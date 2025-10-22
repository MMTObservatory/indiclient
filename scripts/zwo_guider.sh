#!/bin/bash

indi_getprop -h f9indi -m -t 2 > /dev/null & indi_setprop -h f9indi "ZWO CCD ASI1600MM Pro.CCD_EXPOSURE.CCD_EXPOSURE_VALUE=1"
sleep 2
mv ZWO\ CCD\ ASI1600MM\ Pro.CCD1.CCD1.fits zwo_guide.fits
