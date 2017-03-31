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
    def ccd_info(self):
        """
        Get the CCD info about pixel sizes and bits per pixel, etc.
        """
        info_vec = self.get_vector(self.driver, "CCD_INFO")
        info = {}
        for e in info_vec.elements:
            info[e.getName()] = e.get_float()
        return info

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

    @property
    def binning(self):
        """
        Get the X and Y binning that is currently set. Different cameras have different restrictions on how binning
        can be set so configure the @setter on a per class basis.
        """
        bin_vec = self.get_vector(self.driver, "CCD_BINNING")
        binning = {}
        for e in bin_vec.elements:
            binning[e.label] = e.get_int()
        return binning

    @property
    def observer(self):
        obs = self.get_text(self.driver, "FITS_HEADER", "FITS_OBSERVER")
        return obs

    @observer.setter
    def observer(self, string):
        o_vec = self.set_and_send_text(self.driver, "FITS_HEADER", "FITS_OBSERVER", string)

    @property
    def object(self):
        obj = self.get_text(self.driver, "FITS_HEADER", "FITS_OBJECT")
        return obj

    @object.setter
    def object(self, string):
        o_vec = self.set_and_send_text(self.driver, "FITS_HEADER", "FITS_OBJECT", string)

    def connect(self):
        """
        Enable camera connection
        """
        vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CONNECTION", "Connect")
        if self.debug:
            vec.tell()
        self.process_events()
        return vec

    def disconnect(self):
        """
        Disable camera connection
        """
        vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CONNECTION", "Disconnect")
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
        self.observer = "Mount Alignment Telescope"
        self.process_events()


class F9WFSCam(CCDCam):
    """
    Wrap CCDCam, set the driver to the SBIG driver, and point to the server for the F9WFS camera.
    """
    def __init__(self, host="sbig-srv.mmto.arizona.edu", port=7625):
        super(F9WFSCam, self).__init__(host, port, driver="SBIG CCD")
        self.observer = "F/9 WFS"
        self.process_events()
        self.wfs_config()

    @property
    def temperature(self):
        t = self.get_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE")
        return t

    @temperature.setter
    def temperature(self, temp):
        curr_t = self.get_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE")
        t_vec = self.set_and_send_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE", temp)
        if temp < curr_t:
            self.cooling_on()
        return t_vec

    @property
    def cooling_power(self):
        power = self.get_float(self.driver, "CCD_COOLER_POWER", "CCD_COOLER_VALUE")
        return power

    @property
    def cooler(self):
        cooler = self.get_text(self.driver, "CCD_COOLER", "COOLER_ON")
        return cooler

    @property
    def fan(self):
        fan = self.get_text(self.driver, "CCD_FAN", "FAN_ON")
        return fan

    @property
    def binning(self):
        """
        Get the X and Y binning that is currently set. Different cameras have different restrictions on how binning
        can be set so configure the @setter on a per class basis.
        """
        bin_vec = self.get_vector(self.driver, "CCD_BINNING")
        binning = {}
        for e in bin_vec.elements:
            binning[e.label] = e.get_int()
        return binning

    @binning.setter
    def binning(self, bindict):
        """
        Set binning from a dict of form of e.g. {'X':2, 'Y':2}
        """
        if 'X' in bindict:
            if bindict['X'] >= 1:
                x_vec = self.set_and_send_float(self.driver, "CCD_BINNING", "HOR_BIN", int(bindict['X']))

        if 'Y' in bindict:
            if bindict['Y'] >= 1:
                y_vec = self.set_and_send_float(self.driver, "CCD_BINNING", "VER_BIN", int(bindict['Y']))

    def fan_on(self):
        """
        Turn the fan on (DISABLED due to bug in SBIG library)
        """
        #f_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_FAN", "On")
        f_vec = None
        return f_vec

    def fan_off(self):
        """
        Turn the fan off (DISABLED due to bug in SBIG library)
        """
        #f_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_FAN", "Off")
        f_vec = None
        return f_vec

    def cooling_on(self):
        """
        Turn the cooler on
        """
        c_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_COOLER", "On")
        return c_vec

    def cooling_off(self):
        """
        Turn the cooler off
        """
        c_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_COOLER", "Off")
        return c_vec

    def default_config(self):
        """
        Configure camera to full frame and 1x1 binning
        """
        self.binning = {"X": 1, "Y": 1}
        ccdinfo = self.ccd_info
        xl = self.set_and_send_float(self.driver, "CCD_FRAME", "X", 0)
        yl = self.set_and_send_float(self.driver, "CCD_FRAME", "Y", 0)
        xu = self.set_and_send_float(self.driver, "CCD_FRAME", "WIDTH", ccdinfo['CCD_MAX_X'])
        yu = self.set_and_send_float(self.driver, "CCD_FRAME", "HEIGHT", ccdinfo['CCD_MAX_Y'])

    def wfs_config(self):
        """
        Configure camera to be square with 3x3 binning for WFS imaging
        """
        self.binning = {"X": 3, "Y": 3}
        ccdinfo = self.ccd_info
        diff = ccdinfo['CCD_MAX_X'] - ccdinfo['CCD_MAX_Y']

        # interestingly, the starting coords are in binned coords, but the width/height are unbinned
        xl = self.set_and_send_float(self.driver, "CCD_FRAME", "X", int(diff/6))
        yl = self.set_and_send_float(self.driver, "CCD_FRAME", "Y", 0)
        xu = self.set_and_send_float(self.driver, "CCD_FRAME", "WIDTH", ccdinfo['CCD_MAX_Y'])
        yu = self.set_and_send_float(self.driver, "CCD_FRAME", "HEIGHT", ccdinfo['CCD_MAX_Y'])
