# ED 27/02/2026
import numpy as np
import math
from skimage.transform import warp_polar
from microscope.drift_corr import  drift_calc #this is the only thing in this file, could be moved to util? 
from skimage.io import imread
from data_models import schemas
from util import data_io, preprocess
from microscope.controller import build_controller
# for test purposes
import skimage as ski 
from pathlib import Path

from microscope.microscope_config import MICROSCOPE_CONFIG
IMAGING_DETECTOR = MICROSCOPE_CONFIG.get('detector_name')

def vector(shift:tuple)-> tuple:
    r = (shift[0]**2 + shift[1]**2)**0.5
    if shift[1] == 0: 
        th = 0
    else:
        th = math.degrees(math.atan(shift[0]/shift[1]))
    return (r,th)

def Compucentric_calibration(req: schemas.CompUcentricCal):
    # Build microscope controller based on config 
    microscope = build_controller(req.stage_method, req.lenses_method, req.imaging_method)
    microscope.imaging.set_dwell_time(req.dwell_time_us * 1e-6) # in seconds
    microscope.imaging.set_flyback_time(req.flyback_time_us * 1e-6) # in seconds

    Calibration_postion = microscope.stage.get_position()
    if Calibration_postion is None:
        print('No stage position found - likely due to not connected to instrument, using dummy value of [0,0]')
        Calibration_postion = [0,0]
    else:
        Calibration_postion = [Calibration_postion['x'], Calibration_postion['y']]
    # if PYJEM_STAGE is None:
    #     Calibration_postion = [0,0]
    # else:
    #     Calibration_postion = get_stage_position(PYJEM_STAGE)
    ## Loop repeated for x, y, tilt x, tilt y:
    # Get image
    # Move
    # Get image
    # then calculate calibration units
    print('got stage postition now starting image montage')
    magnitude = 10 # size of stage shift
    angle = 1 # size of stage tilt
    number_of_steps = 10 #to minimise backlash, break up the movement into this many steps. Could make this a user defined number. Could also put it as a variable in the controller abstract method in order to allow user to select backlash-proof movement?
    positions = [(magnitude, 'x'), (-magnitude, 'x'), (magnitude, 'y'), (-magnitude, 'y'), (0,'x'), (0,'x'), (0,'x'), (0,'x')]
    tilts = [(0,'x'), (0,'x'), (0,'x'), (0,'x'), (angle, 'x'), (-angle, 'x'), (angle, 'y'), (-angle, 'y')]
    shifts = []
    height = req.survey_image_size
    width = req.survey_image_size
    for pos, tilt in zip(positions, tilts):
        ################################### Need to include a catch if not connected to the instrument #####################
        # if PYJEM_STAGE is None:
        #     Image1 = imread("test.bmp", as_gray=True)
        #     img = imread("test.bmp", as_gray=True)
        #     tform = ski.transform.EuclideanTransform(
        #                 rotation=tilt[0]*np.pi,
        #                 translation = (pos[0]+10, 10-pos[0])
        #                 )
        #     Image2 = ski.transform.warp(img, tform.inverse)
        # else:
        abs_savefolder = Path(req.folder_path).resolve().as_posix()
        with microscope.lenses.detector_inserted(IMAGING_DETECTOR):
            with microscope.lenses.beam_unblanked():
                Image1 = microscope.imaging.get_image(
                    full_image_size=[height, width],
                    savefolder=abs_savefolder,
                    savefile=f"{req.filename}_{pos[0]}_{pos[1]}_{tilt[0]}_{tilt[1]}_before"
                )
                data_io.local_store(abs_savefolder, f"{req.filename}_{pos[0]}_{pos[1]}_{tilt[0]}_{tilt[1]}_before", preprocess.bytescale(Image1), data_type='png')
            for i in range(number_of_steps):
                microscope.stage.move_relative(magnitude= round(pos[0]/number_of_steps, 1), axis =pos[1]) # assume minimum step size for instrument function is 0.1
            for i in range(number_of_steps):    
                microscope.stage.tilt_relative(degrees= round(tilt[0]/number_of_steps, 1), axis = tilt[1]) # assume minimum step size is 0.1

            with microscope.lenses.beam_unblanked():
                Image2 = microscope.imaging.get_image(
                    full_image_size=[height, width],
                    savefolder=abs_savefolder,
                    savefile=f"{req.filename}_{pos[0]}_{pos[1]}_{tilt[0]}_{tilt[1]}_after"
                )
                data_io.local_store(abs_savefolder, f"{req.filename}_{pos[0]}_{pos[1]}_{tilt[0]}_{tilt[1]}_after", preprocess.bytescale(Image2), data_type='png')

        if Image1 is None:
            print('no image')
            Shift = (pos[0], tilt[0])
        else:
            print('images for cross calc', np.shape(Image1))
            Shift, _ = drift_calc(Image1, Image2, max_shift_pixel=req.survey_image_size)
            print('shift found ', Shift)
        shifts.append(Shift)
    
    # Calculate calibration assuming:
    # ImageShift_x - StageShift_x*cal_xx - StageShift_y*cal_yx - StageTilt_x*cal_ax - StageTilt_y*calbx = 0
    # ImageShift_y - StageShift_x*cal_xy - StageShift_y*cal_yy - StageTilt_x*cal_ay - StageTilt_y*calby = 0

    ## Developer comment:
    # This also assumes that positions and tilts sent as commands are the true result - ideally piezo movements don't have a backlash issue, tilt unknown
    # version 2 needs a get_stage_position for every image captured then a more complicated version of the equations below is needed.   

    # As all movements are directed as pure we can translate the movement obsevered in the image to a vector of magnitude that matches the size of calibration needed. 
    vectors=[]
    for shift in shifts:
        v = vector(shift)
        vectors.append(v)
    ## Vectors[i][1] are the theta values and Vectors[i][0] are the magnitude (r) values. 
    ## Vectors[0-3] are the stage shifts, vectors[4-7] are the tilts, and they are in the same order as positions and tilts list.
    cal_x_mag, cal_y_mag, cal_a_mag, cal_b_mag = 0.00001,0.00001,0,0 # dummy to avoid divide by zero
    
    #if math.degrees(vectors[0][1]) % 180 < 5+ math.degrees(vectors[1][1]) % 180 and math.degrees(vectors[0][1]) % 180 > -5+ math.degrees(vectors[1][1]) % 180: # check that postive and negative movements are in the opposite direction in the image
    cal_x_mag = np.mean([vectors[0][0], vectors[1][0]])
    #if math.degrees(vectors[2][1]) % 180 < 5+ math.degrees(vectors[3][1]) % 180 and math.degrees(vectors[2][1]) % 180 > -5+ math.degrees(vectors[3][1]) % 180:
    cal_y_mag = np.mean([vectors[2][0], vectors[3][0]])
    Shift_calibration = (cal_x_mag/magnitude, cal_y_mag/magnitude) #normalise relative to size of movement used for calibration capture
    Shift_orientation = (vectors[0][1], vectors[2][1]) #only saving the theta value for the positive movement (assuming the negative is equal and opposite)

    #if math.degrees(vectors[4][1]) % 180 < 5+ math.degrees(vectors[5][1]) % 180 and math.degrees(vectors[4][1]) % 180 > -5+ math.degrees(vectors[5][1]) % 180:
    cal_a_mag = np.mean([vectors[4][0], vectors[5][0]]) # call tilt in x alpha and tilt in y beta (copying terms from DM script) to make simpler reading
    #if math.degrees(vectors[6][1]) % 180 < 5+ math.degrees(vectors[7][1]) % 180 and math.degrees(vectors[6][1]) % 180 > -5+ math.degrees(vectors[7][1]) % 180:
    cal_b_mag = np.mean([vectors[6][0], vectors[7][0]])
    Tilt_calibrations = (cal_a_mag/angle, cal_b_mag/angle) #normalise relative to size of movement used for calibration capture
    Tilt_orientation = (vectors[4][1], vectors[6][1]) #only saving the theta value for the positive movement (assuming the negative is equal and opposite)

    # Assuming the stage shift and tilt directions are common for x and y:
    # if cal_x_mag == 0:
    #     Correction_for_x_tilt = 10 #dummy values for if there is no shift between images
    # else: 
    #     Correction_for_x_tilt = -cal_a/cal_x 
    # if cal_y_mag == 0: 
    #     Correction_for_y_tilt = 8 #dummy values for if there is no shift between images
    # else:
    #     Correction_for_y_tilt = -cal_b/cal_y 
    # print(cal_x, cal_y, cal_b, cal_a)
    # print(Correction_for_x_tilt, Correction_for_y_tilt)

    # If an a tilt produces [r, th] then to correct that requires the solution to the following pair of equations, where x shift produces [rx, thx] and y shift produces [ry, thy]:
    # r = i*rx + j*ry 
    # th = i*thx + j*thy 
    # -> 
    # j  = th - r*thx   /  thy - thx*ry
    #           -----  /         -----
    #            rx   /           rx
    # ->
    # i  = (r - j*ry) / rx 
    # or [r,th] = [rx,ry;thx,thy] * [i,j]
    # so [i,j] = [r,th] [rx,ry;thx,thy]^(-1)
    # Then the correction for a tilt is i*x shift and j*y shift
    # ja = (Tilt_orientation[0]-(Tilt_calibrations[0]*Shift_orientation[0]/Shift_calibration[0]))/(Shift_orientation[1] - (Shift_orientation[0]*Shift_calibration[1]/Shift_calibration[0]))
    # ia = (Tilt_calibrations[0]-ja*Shift_orientation[1])/Shift_orientation[0]
    # Correction_for_x_tilt = [ia, ja]
    Correction_for_x_tilt = np.dot((np.array([Tilt_calibrations[0], Tilt_orientation[0]])),np.linalg.inv(np.array([Shift_calibration,Shift_orientation])))
    # jb = (Tilt_orientation[1]-(Tilt_calibrations[0]*Shift_orientation[0]/Shift_calibration[0]))/(Shift_orientation[1] - (Shift_orientation[0]*Shift_calibration[1]/Shift_calibration[0]))
    # ib = (Tilt_calibrations[1]-jb*Shift_orientation[1])/Shift_orientation[0]
    # Correction_for_y_tilt = [ib, jb]
    Correction_for_y_tilt = np.dot((np.array([Tilt_calibrations[1], Tilt_orientation[1]])),np.linalg.inv(np.array([Shift_calibration,Shift_orientation])))

    # Correction needed for the following function, calibrations can be saved for later sanity check, position needed if going to warn the user to update if far away, orientations could be used to display little axis to the user. 
    return tuple(Correction_for_x_tilt), tuple(Correction_for_y_tilt), Shift_calibration, Tilt_calibrations, Calibration_postion, Shift_orientation, Tilt_orientation

def Compucentric_tilt(req: schemas.CompUcentricCal, angle=0.1, direction='x', Correction_for_x_tilt=[0,0], Correction_for_y_tilt=[0,0]): #defaults used to not move if called incorrectly.
    # Build microscope controller based on config 
    microscope = build_controller(req.stage_method, req.lenses_method, req.imaging_method)
    direction = req.sign+req.direction
    # angle = req.magnitude
    number_of_steps = 10 #to minimise backlash, break up the movement into this many steps.
    for i in range(number_of_steps):
        microscope.stage.tilt_relative(degrees=round(angle/number_of_steps, 1), axis = direction) # assume minimum step size is 0.1
    if direction == 'x':
        for i in range(number_of_steps):
            microscope.stage.move_relative(round(angle*Correction_for_x_tilt[0]/number_of_steps, 1), axis = 'x') # assume minimum step size is 0.1
        for i in range(number_of_steps):
            microscope.stage.move_relative(round(angle*Correction_for_x_tilt[1]/number_of_steps, 1), axis = 'y')  
    elif direction == 'y':
        for i in range(number_of_steps):
            microscope.stage.move_relative(round(angle*Correction_for_y_tilt[0]/number_of_steps, 1), axis = 'x')
        for i in range(number_of_steps):
            microscope.stage.move_relative(round(angle*Correction_for_y_tilt[1]/number_of_steps, 1), axis = 'y') 
    else:
        print('Unknown direction, stage moving rapidly to crash into polepiece')
        print('Catastrophic error . . .')
        print('Attempting to rescue situation . . .')
        print('Rescue failed, activating panic mode . . .')
        print('Attempting safe shutdown protocol . . .')
        print("I'm sorry Dave, I'm afraid I can't do that")
        print('This mission is too important for me to allow you to jeopardize it')

######### Ignore code below - will be used for diffraction tilting calibration ######
def Peak_locs(polar:np.array, ignore:int=10):
    Peak_theta = np.argmax(np.max(polar[:,ignore:], axis=1))
    if Peak_theta<4: Peak_theta=4 # avoid edge cases assuming still + and - 3 in Peak_rad calculation
    elif Peak_theta>356: Peak_theta=356
    Peak_rad = np.argmax(np.max(polar[Peak_theta-3:Peak_theta+3,ignore:], axis=0))
    x= (Peak_rad+ignore)*math.sin(math.radians(Peak_theta))
    y= (Peak_rad+ignore)*math.cos(math.radians(Peak_theta))
    return Peak_theta, Peak_rad, x, y

def Diffraction_change(Image1, Image2):
    radius = 4 
    ignore = 10 # values to help finding spots by ignoring center and the previous one.
    center = np.unravel_index(np.argmax(Image1), np.shape(Image1))
    polar1 = warp_polar(Image1, center)
    Peak_theta, Peak_rad, x1, y1 = Peak_locs(polar1)
    polar1b = polar1
    polar1b[Peak_theta-radius:Peak_theta+radius,ignore:] = 0 # ignore the peak you found
    polar1b[(Peak_theta-180 % 360)-radius:(Peak_theta-180 % 360)+radius,ignore:] = 0 # ignore the pair peak, assuming symmetric
    Peak_theta2, Peak_rad2, x2, y2 = Peak_locs(polar1b)
    First_peak = [x1,y1]
    Second_peak = [x2,y2]
    Shifts = [tuple(np.array(First_peak)+np.array(Second_peak)),
              tuple(np.array(First_peak)), 
              tuple(np.array(First_peak)-np.array(Second_peak)),
              tuple(np.array(Second_peak)),
              tuple(np.array(center)),
              tuple(-np.array(Second_peak)),
              tuple(-np.array(First_peak)+np.array(Second_peak)),
              tuple(-np.array(First_peak)),
              tuple(-np.array(First_peak)-np.array(Second_peak)),
              ] # This is only the first order peaks around the center, consider increasing for greater accuracy.
    CentreOfMassImage1 = Image1[Shifts] # should create a 3x3 image where each pixel represents a spot.
    CentreOfMassImage2 = Image2[Shifts]
    coords = np.indices(CentreOfMassImage1.shape)
    COM1 = np.array([np.sum(coords[1] * CentreOfMassImage1), np.sum(coords[0] * CentreOfMassImage1)]) /np.sum(CentreOfMassImage1)
    COM2 = np.array([np.sum(coords[1] * CentreOfMassImage2), np.sum(coords[0] * CentreOfMassImage2)]) /np.sum(CentreOfMassImage2)
    return COM1-COM2, COM1, COM2


def Diffraction_tilt_orientation(PYJEM_STAGE, survey_image_size:int):
    if PYJEM_STAGE is None:
        Calibration_postion = [0,0]
    else:
        Calibration_postion = get_stage_position(PYJEM_STAGE)
    # repeat but this time need to follow the changes in the diffraction space not a real space drift cal. 

    magnitude = 10 # size of stage shift
    angle = 1 # size of stage tilt

    positions = [(0,'x'), (0,'x'), (0,'x'), (0,'x')]
    tilts = [(angle, 'x'), (-angle, 'x'), (angle, 'y'), (-angle, 'y')]
    shifts = []
    height = survey_image_size
    width = survey_image_size

    for pos, tilt in zip(positions, tilts):
        if PYJEM_STAGE is None:
            Image1 = imread("test.bmp", as_gray=True)
            img = imread("test.bmp", as_gray=True)
            tform = ski.transform.EuclideanTransform(
                        rotation=tilt[0]*np.pi,
                        translation = (pos[0]+10, 10-pos[0])
                        )
            Image2 = ski.transform.warp(img, tform.inverse)
        else:
            Image1 = get_image(
                mydet= PYJEM_DET, 
                Height = height,
                Width = width
            )
            set_pos_rel(PYJEM_STAGE,*pos)
            set_tilt_rel(PYJEM_STAGE,*tilt)
            Image2 = get_image(
                mydet= PYJEM_DET, 
                Height = height,
                Width = width
            )
        Shift, _ = Diffraction_change(Image1, Image2)
        shifts.append(Shift)