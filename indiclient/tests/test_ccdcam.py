from ..indicam import CCDCam


def test_ccdcam():
    cam = CCDCam("localhost", 7624)
    assert(cam is not None)
    cam.quit()
