# Licensed under GPL3 (see LICENSE)
# coding=utf-8

"""
Classes and utility functions for communicating with SBIG cameras via the INDI protocol, http://www.indilib.org.
"""

import time
import io

from astropy.io import fits

from .indiclient import indiclient


class CCDCam(indiclient):
    """
    Wrap indiclient.indiclient with some camera-specific utility functions to simplify things like taking,
    exposures, configuring camera binning, etc.
    """
    def __init__(self, host, port, driver="CCD Simulator", debug=True):
        super(CCDCam, self).__init__(host, port)
        self.enable_blob()
        self.driver = driver
        self.debug = debug
        if not self.connected:
            self.connect()

        # run this to clear any queued events
        self.process_events()
        self.defvectorlist = []

    @property
    def connected(self):
        """
        Check connection status and return True if connected, False otherwise.
        """
        status = self.get_text(self.driver, "CONNECTION", "CONNECT")
        if status == 'On':
            return True
        else:
            return False

    def connect(self):
        """
        Enable camera connection
        """
        vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CONNECTION", "Connect")
        if self.debug:
            vec.tell()
        return vec

    def disconnect(self):
        """
        Disable camera connection
        """
        vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CONNECTION", "Disonnect")
        if self.debug:
            vec.tell()
        return vec

    def _default_def_handler(self, vector, indi):
        """
        Overload the default vector handler to do a vector.tell() so it's clear what's going on
        """
        if self.debug:
            vector.tell()
        pass

    def expose(self, exptime=1.0, exptype="Light"):
        """
        Take exposure and return FITS data
        """
        if exptype not in ["Light", "Dark", "Bias", "Flat"]:
            raise Exception("Invalid exposure type, %s. Must be one of 'Light', 'Dark', 'Bias', or 'Flat'." % exptype)

        if exptime < 0.0 or exptime > 3600.0:
            raise Exception("Invalid exposure time, %f. Must be >= 0 and <= 3600 sec." % exptime)

        ft_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_FRAME_TYPE", exptype)
        if self.debug:
            ft_vec.tell()

        exp_vec = self.set_and_send_float(self.driver, "CCD_EXPOSURE", "CCD_EXPOSURE_VALUE", exptime)
        if self.debug:
            exp_vec.tell()

        self.defvectorlist = []
        fitsdata = None
        run = True

        while run:
            self.process_receive_vector_queue()
            while self.receive_event_queue.empty() is False:
                vector = self.receive_event_queue.get()
                if vector.tag.get_type() == "BLOBVector":
                    print("reading out...")
                    blob = vector.get_first_element()
                    if blob.get_plain_format() == ".fits":
                        buf = io.BytesIO(blob.get_data())
                        fitsdata = fits.open(buf)
                    run = False
                    break
            time.sleep(0.1)
        return fitsdata


class MATCam(CCDCam):
    """
    Wrap CCDCam, set the driver to the SBIG driver, and point to the server for the MAT camera.
    """
    def __init__(self, host="sbig-srv.mmto.arizona.edu", port=7624):
        super(MATCam, self).__init__(host, port, driver="SBIG CCD")
