from indiclient.indicam import CCDCam


def test_ccdcam():
    """
    basic sanity check to build and take down camera object
    """
    cam = CCDCam("localhost", 7624)
    assert cam is not None
    assert cam.connected
    cam.quit()


def test_ccdtemp():
    """
    testing reading/setting camera temp
    """
    cam = CCDCam("localhost", 7624)
    t = cam.temperature
    assert t == 20.0
    cam.temperature = 20.0
    assert cam.temperature == 20.0
    cam.quit()


def test_ccdinfo():
    """
    test reading ccd info
    """
    cam = CCDCam("localhost", 7624)
    assert cam.ccd_info is not None
    cam.quit()


def test_observer():
    """
    test reading/setting observer
    """
    cam = CCDCam("localhost", 7624)
    observer = "foo"
    cam.observer = observer
    assert cam.observer == observer
    cam.quit()


def test_object():
    """
    test reading/setting target object name
    """
    cam = CCDCam("localhost", 7624)
    obj = "mars"
    cam.object = obj
    assert cam.object == obj
    cam.quit()


def test_cooler():
    """
    test checking cooler status
    """
    cam = CCDCam("localhost", 7624)
    assert cam.cooler is not None
    cam.quit()


def test_fan():
    """
    test checking fan status (testing simulator has no fan)
    """
    cam = CCDCam("localhost", 7624)
    assert cam.fan is None
    cam.quit()


def test_filters():
    """
    test reading/setting filters
    """
    cam = CCDCam("localhost", 7624)
    filters = cam.filters
    assert filters is not None
    f1 = filters[0]
    f2 = filters[-1]
    cam.filter = f2
    assert cam.filter == f2
    cam.filter = 0
    assert cam.filter == f1
    cam.quit()


def test_binning():
    """
    test reading/setting binning
    """
    cam = CCDCam("localhost", 7624)
    binning = cam.binning
    assert binning is not None
    bindict = {'X': 2, 'Y': 2}
    cam.binning = bindict
    assert cam.binning == bindict
    cam.quit()


def test_frame():
    """
    test reading/setting readout region
    """
    cam = CCDCam("localhost", 7624)
    frame = cam.frame
    assert frame is not None
    newframe = {
        'X': 1,
        'Y': 1,
        'width': 100,
        'height': 100
    }
    cam.frame = newframe
    assert cam.frame == newframe
    cam.quit()


def test_connect():
    """
    test disconnecing and then reconnecting
    """
    cam = CCDCam("localhost", 7624)
    v = cam.disconnect()
    assert v is not None
    v = cam.connect()
    assert v is not None
    t = cam.temperature
    assert t == 20.0
    cam.quit()


def text_expose():
    """
    test taking an exposure
    """
    cam = CCDCam("localhost", 7624)
    data = cam.expose()
    assert data is not None
    cam.quit()
