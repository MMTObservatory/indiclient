# Licensed under GPL3 (see LICENSE)
# coding=utf-8

"""
Classes and utility functions for communicating with cameras via the INDI protocol, http://www.indilib.org.
"""

import time
import io

import logging
import logging.handlers

from astropy.io import fits

from .indiclient import indiclient

log = logging.getLogger("")
log.setLevel(logging.INFO)


class CCDCam(indiclient):
    """
    Wrap indiclient.indiclient with some camera-specific utility functions to simplify things like taking,
    exposures, configuring camera binning, etc.
    """
    def __init__(self, host, port, driver="CCD Simulator", debug=True):
        super(CCDCam, self).__init__(host, port)
        self.camera_name = "MMTO Default"
        self.enable_blob()
        self.driver = driver
        self.debug = debug
        if not self.connected:
            self.connect()
            time.sleep(2)

        # run this to clear any queued events
        self.process_events()
        self.defvectorlist = []
        self.vector_dict = {v.name: v for v in self.indivectors.list}

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

    @property
    def temperature(self):
        self.process_events()
        t = self.get_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE")
        return t

    @temperature.setter
    def temperature(self, temp):
        curr_t = self.get_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE")
        t_vec = self.set_and_send_float(self.driver, "CCD_TEMPERATURE", "CCD_TEMPERATURE_VALUE", temp)
        self.process_events()

    @property
    def cooling_power(self):
        self.process_events()
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
    def frame_types(self):
        types = [e.label for e in self.get_vector(self.driver, "CCD_FRAME_TYPE").elements]
        return types

    @property
    def filters(self):
        """
        Return list of names of installed filters
        """
        filters = [e.get_text() for e in self.get_vector(self.driver, "FILTER_NAME").elements]
        return filters

    @property
    def filter(self):
        slot = int(self.get_float(self.driver, "FILTER_SLOT", "FILTER_SLOT_VALUE")) - 1  # filter slots 1-indexed
        if slot >= 0 and slot < len(self.filters):
            f = self.filters[slot]
        else:
            f = None
        return f

    @filter.setter
    def filter(self, f):
        if isinstance(f, int):
            if f >= 0 and f < len(self.filters):
                v = self.set_and_send_float(self.driver, "FILTER_SLOT", "FILTER_SLOT_VALUE", f+1)
        else:
            if f in self.filters:
                v = self.set_and_send_float(self.driver, "FILTER_SLOT", "FILTER_SLOT_VALUE", self.filters.index(f)+1)

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
                log.info("Setting X binning to %d" % int(bindict['X']))

        if 'Y' in bindict:
            if bindict['Y'] >= 1:
                y_vec = self.set_and_send_float(self.driver, "CCD_BINNING", "VER_BIN", int(bindict['Y']))
                log.info("Setting Y binning to %d" % int(bindict['Y']))

    @property
    def frame(self):
        """
        Get the frame configuration of the CCD: X lower, Y lower, width, and height
        """
        xl = self.get_float(self.driver, "CCD_FRAME", "X")
        yl = self.get_float(self.driver, "CCD_FRAME", "Y")
        xu = self.get_float(self.driver, "CCD_FRAME", "WIDTH")
        yu = self.get_float(self.driver, "CCD_FRAME", "HEIGHT")
        frame_info = {
            'X': xl,
            'Y': yl,
            'width': xu,
            'height': yu
        }
        return frame_info

    @frame.setter
    def frame(self, framedict):
        """
        Configure area of CCD to readout where framedict is of the form:
        {
            "X": int - lower X value of readout region
            "Y": int - lower Y value of readout region
            "width": int - width of the readout region
            "height": int - height of the readout region
        }
        """
        ccdinfo = self.ccd_info
        if 'X' in framedict:
            if framedict['X'] >= 0 and framedict['X'] <= ccdinfo['CCD_MAX_X']:
                xl = self.set_and_send_float(self.driver, "CCD_FRAME", "X", int(framedict['X']))
                log.info("Setting lower X to %d" % int(framedict['X']))
                if 'width' in framedict:
                    newwidth = min(framedict['width'], ccdinfo['CCD_MAX_X']-framedict['X'])
                    if newwidth >= 1:
                        xu = self.set_and_send_float(self.driver, "CCD_FRAME", "WIDTH", int(newwidth))
                        log.info("Setting width to %d" % int(newwidth))
        if 'Y' in framedict:
            if framedict['Y'] >= 0 and framedict['Y'] <= ccdinfo['CCD_MAX_Y']:
                yl = self.set_and_send_float(self.driver, "CCD_FRAME", "Y", int(framedict['Y']))
                log.info("Setting lower Y to %d" % int(framedict['Y']))
                if 'height' in framedict:
                    newheight = min(framedict['height'], ccdinfo['CCD_MAX_Y']-framedict['Y'])
                    if newheight >= 1:
                        yu = self.set_and_send_float(self.driver, "CCD_FRAME", "HEIGHT", int(newheight))
                        log.info("Setting height to %d" % int(newheight))

    def connect(self):
        """
        Enable camera connection
        """
        vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CONNECTION", "Connect")
        if self.debug and vec is not None:
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

    def cooling_on(self):
        """
        Turn the cooler on
        """
        c_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_COOLER", "On")
        self.process_events()
        return c_vec

    def cooling_off(self):
        """
        Turn the cooler off
        """
        c_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_COOLER", "Off")
        self.process_events()
        return c_vec

    def expose(self, exptime=1.0, exptype="Light"):
        """
        Take exposure and return FITS data
        """
        if exptype not in self.frame_types:
            raise Exception("Invalid exposure type, %s. Must be one of %s'." % (exptype, repr(self.frame_types)))

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

        t = time.time()
        timeout = exptime + 10.0

        while run:
            self.process_receive_vector_queue()
            while self.receive_event_queue.empty() is False:
                vector = self.receive_event_queue.get()
                if vector.tag.get_type() == "BLOBVector":
                    log.info("Reading FITS image out...")
                    blob = vector.get_first_element()
                    if blob.get_plain_format() == ".fits":
                        buf = io.BytesIO(blob.get_data())
                        fitsdata = fits.open(buf)
                        if 'FILTER' not in fitsdata[0].header:
                            fitsdata[0].header['FILTER'] = self.filter
                        fitsdata[0].header['CAMERA'] = self.camera_name
                    run = False
                    break
                if vector.tag.get_type() == "message":
                    msg = vector.get_text()
                    if "ERROR" in msg:
                        log.error(msg)
                    else:
                        log.info(msg)
            if ((time.time() - t) > timeout):
                log.warning("Exposure timed out.")
                break
            time.sleep(0.1)
        return fitsdata


class ASICam(CCDCam):
    """
    Wrap CCDCam, set driver to ASI CCD, and point to localhost by default.
    """
    def __init__(self, host='localhost', port=7624):
        super(ASICam, self).__init__(host, port, driver="ASI CCD")
        self.camera_name = "ZWO ASI Camera"
        self.process_events()

    @property
    def filters(self):
        return ["N/A"]

    @property
    def filter(self):
        return "N/A"

    @filter.setter
    def filter(self, f):
        pass

    @property
    def gain(self):
        self.process_events()
        gain = self.get_float(self.driver, "CCD_CONTROLS", "Gain")
        return gain

class RATCam(CCDCam):
    """
    Wrap CCDCam, set the driver to the SBIG driver, and point to the server for the RAT camera, a monochrome ST-IM
    """
    def __init__(self, host="ratcam.mmto.arizona.edu", port=7624):
        super(RATCam, self).__init__(host, port, driver="SBIG CCD")
        self.observer = "Rotator Alignment Telescope"
        self.camera_name = "RATcam"
        self.process_events()

    # turn off a bunch of functionality that doesn't apply to the ST-I series
    @property
    def temperature(self):
        return None

    @property
    def cooling_power(self):
        return None

    @property
    def cooler(self):
        return None

    @property
    def fan(self):
        return None

    @property
    def filters(self):
        return ["N/A"]

    @property
    def filter(self):
        return "N/A"

    @filter.setter
    def filter(self, f):
        pass

    def cooling_on(self):
        pass

    def cooling_off(self):
        pass


class SimCam(CCDCam):
    """
    The INDI CCD simulator device does not have a vector for cooling power. Set this sub-class up to work around that.
    """
    def __init__(self, host="localhost", port=7624):
        super(SimCam, self).__init__(host, port, driver="CCD Simulator")
        self.observer = "INDI CCD Simulator"
        self.camera_name = "SimCam"

    @property
    def cooling_power(self):
        return None


class MATCam(CCDCam):
    """
    Wrap CCDCam, set the driver to the SBIG driver, and point to the server to an ST-402 with BVR filters.
    The specific camera is ID #06111391 and has Johnson BVR filters installed.  It is currently installed on the MAT.
    """
    def __init__(self, host="matcam.mmto.arizona.edu", port=7624):
        super(MATCam, self).__init__(host, port, driver="SBIG CCD")

        # enable filter wheel
        self.enable_cfw()

        self.observer = "Mount Alignment Telescope"
        self.camera_name = "MATcam"
        self.process_events()

        time.sleep(1)

    def enable_cfw(self):
        type_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CFW_TYPE", "CFW-402")
        cfw_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CFW_CONNECTION", "Connect")
        self.process_events()
        return cfw_vec, type_vec

    def disable_cfw(self):
        cfw_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CFW_CONNECTION", "Disconnect")
        self.process_events()
        return cfw_vec


class F9WFSCam(CCDCam):
    """
    Wrap CCDCam, set the driver to the SBIG driver, and point to the server for the F9WFS camera.
    """
    def __init__(self, host="f9indi.mmto.arizona.edu", port=7624):
        super(F9WFSCam, self).__init__(host, port, driver="SBIG CCD")
        self.camera_name = "F/9 WFS"
        self.connect()
        time.sleep(1)
        self.process_events()

    @property
    def filters(self):
        return ["N/A"]

    @property
    def filter(self):
        return "N/A"

    @filter.setter
    def filter(self, f):
        pass

    def wfs_setup(self):
        """
        Configure camera for WFS use. Set observer and set up detector config
        """
        self.process_events()
        self.observer = "F/9 WFS"
        self.wfs_config()

    def fan_on(self):
        """
        Turn the fan on (DISABLED due to bug in SBIG library)
        """
        # f_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_FAN", "On")
        f_vec = None
        return f_vec

    def fan_off(self):
        """
        Turn the fan off (DISABLED due to bug in SBIG library)
        """
        # f_vec = self.set_and_send_switchvector_by_elementlabel(self.driver, "CCD_FAN", "Off")
        f_vec = None
        return f_vec

    def default_config(self):
        """
        Configure camera to full frame and 1x1 binning
        """
        self.binning = {"X": 1, "Y": 1}
        ccdinfo = self.ccd_info
        framedict = {
            'X': 0,
            'Y': 0,
            'width': int(ccdinfo['CCD_MAX_X']),
            'height': int(ccdinfo['CCD_MAX_Y'])
        }
        self.frame = framedict

    def wfs_subim(self):
        ccdinfo = self.ccd_info
        diff = ccdinfo['CCD_MAX_X'] - ccdinfo['CCD_MAX_Y']

        binning = self.binning

        # interestingly, the starting coords are in binned coords, but the width/height are unbinned
        framedict = {
            'X': int(diff/6),
            'Y': 0,
            'width': int(ccdinfo['CCD_MAX_Y']),
            'height': int(ccdinfo['CCD_MAX_Y'])
        }
        self.frame = framedict

    def wfs_config(self):
        """
        Configure camera to be square with 3x3 binning for WFS imaging
        """
        self.binning = {"X": 3, "Y": 3}
        self.wfs_subim()
