import numpy as np
import cv2
# Identify pixels above the threshold
# Threshold of RGB > 160 does a nice job of identifying ground pixels only
def color_thresh(img, rgb_thresh=(160, 160, 160)):
    # Create an array of zeros same xy size as img, but single channel
    color_select = np.zeros_like(img[:,:,0])
    # Require that each pixel be above all three threshold values in RGB
    # above_thresh will now contain a boolean array with "True"
    # where threshold was met
    above_thresh = (img[:,:,0] > rgb_thresh[0]) \
                & (img[:,:,1] > rgb_thresh[1]) \
                & (img[:,:,2] > rgb_thresh[2])
    # Index the array of zeros with the boolean array and set to 1
    color_select[above_thresh] = 1
    # Return the binary image
    return color_select

# Define a function to convert from image coords to rover coords
def rover_coords(binary_img):
    # Identify nonzero pixels
    ypos, xpos = binary_img.nonzero()
    # Calculate pixel positions with reference to the rover position being at the 
    # center bottom of the image.  
    x_pixel = -(ypos - binary_img.shape[0]).astype(np.float)
    y_pixel = -(xpos - binary_img.shape[1]/2 ).astype(np.float)
    return x_pixel, y_pixel


# Define a function to convert to radial coords in rover space
def to_polar_coords(x_pixel, y_pixel):
    # Convert (x_pixel, y_pixel) to (distance, angle) 
    # in polar coordinates in rover space
    # Calculate distance to each pixel
    dist = np.sqrt(x_pixel**2 + y_pixel**2)
    # Calculate angle away from vertical for each pixel
    angles = np.arctan2(y_pixel, x_pixel)
    return dist, angles

# Define a function to map rover space pixels to world space
def rotate_pix(xpix, ypix, yaw):
    # Convert yaw to radians
    yaw_rad = yaw * np.pi / 180
    xpix_rotated = (xpix * np.cos(yaw_rad)) - (ypix * np.sin(yaw_rad))
                            
    ypix_rotated = (xpix * np.sin(yaw_rad)) + (ypix * np.cos(yaw_rad))
    # Return the result  
    return xpix_rotated, ypix_rotated

def translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale): 
    # Apply a scaling and a translation
    xpix_translated = (xpix_rot / scale) + xpos
    ypix_translated = (ypix_rot / scale) + ypos
    # Return the result  
    return xpix_translated, ypix_translated


# Define a function to apply rotation and translation (and clipping)
# Once you define the two functions above this function should work
def pix_to_world(xpix, ypix, xpos, ypos, yaw, world_size, scale):
    # Apply rotation
    xpix_rot, ypix_rot = rotate_pix(xpix, ypix, yaw)
    # Apply translation
    xpix_tran, ypix_tran = translate_pix(xpix_rot, ypix_rot, xpos, ypos, scale)
    # Perform rotation, translation and clipping all at once
    x_pix_world = np.clip(np.int_(xpix_tran), 0, world_size - 1)
    y_pix_world = np.clip(np.int_(ypix_tran), 0, world_size - 1)
    # Return the result
    return x_pix_world, y_pix_world

# Define a function to perform a perspective transform
def perspect_transform(img, src, dst):
    if src is None or dst is None:
        print("error")
        return None
           
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (img.shape[1], img.shape[0]))# keep same size as input image
    
    return warped

def get_rocks(img, lvls = (100, 100, 10)):
    rockpix = (img[:, :, 0]> lvls[0])\
            &(img[:, :, 1]> lvls[1])\
            &(img[:, :, 2]> lvls[2])
    color_select = np.zeros_like(img[:, :, 0])
    color_select[rockpix] = 1
    return color_select

def rect_mask(warped_image, width: int = 300, height: int =0):
    '''
    A rectangular mask that should be applied on
    the  prespective transformed image after thresholding
    the mask is always centered at the bottom center of the image'''
    if height == 0:
        height = warped_image.shape[0]
    mask = np.zeros_like(warped_image)
    xcenter = int(warped_image.shape[1]/2)
    mask[-height :, xcenter-int(width/2): xcenter + int(width/2)] =1
    output = np.bitwise_and(warped_image, mask)
    return output

# Apply the above functions in succession and update the Rover state accordingly
def perception_step(Rover):
    # Perform perception steps to update Rover()
    # TODO: 
    # NOTE: camera image is coming to you in Rover.img
    # 1) Define source and destination points for perspective transform
    # 2) Apply perspective transform
    # 3) Apply color threshold to identify navigable terrain/obstacles/rock samples
    # 4) Update Rover.vision_image (this will be displayed on left side of screen)
        # Example: Rover.vision_image[:,:,0] = obstacle color-thresholded binary image
        #          Rover.vision_image[:,:,1] = rock_sample color-thresholded binary image
        #          Rover.vision_image[:,:,2] = navigable terrain color-thresholded binary image

    # 5) Convert map image pixel values to rover-centric coords
    # 6) Convert rover-centric pixel values to world coordinates
    # 7) Update Rover worldmap (to be displayed on right side of screen)
        # Example: Rover.worldmap[obstacle_y_world, obstacle_x_world, 0] += 1
        #          Rover.worldmap[rock_y_world, rock_x_world, 1] += 1
        #          Rover.worldmap[navigable_y_world, navigable_x_world, 2] += 1

    # 8) Convert rover-centric pixel positions to polar coordinates
    # Update Rover pixel distances and angles
        # Rover.nav_dists = rover_centric_pixel_distances
        # Rover.nav_angles = rover_centric_angles
    debuggingPipe = []
    dst_size = 5
    bottom_offset = 6
    image = Rover.img
    source = np.array([
        [14, 140],
        [301, 140],
        [200, 96],
        [118, 96]], np.float32)
    destination = np.array([
        [image.shape[1]/2 - dst_size, image.shape[0]-bottom_offset],
        [image.shape[1]/2 + dst_size, image.shape[0] - bottom_offset],
        [image.shape[1]/2 + dst_size, image.shape[0] - 2*dst_size - bottom_offset],
        [image.shape[1]/2 - dst_size, image.shape[0] - 2*dst_size - bottom_offset]
    ], np.float32)

    warped = perspect_transform(image, source, destination)
    debuggingPipe.append(warped)

    threshed = color_thresh(warped)
    debuggingPipe.append(threshed*255)

    threshed_masked = rect_mask(threshed, width = 80)
    debuggingPipe.append(threshed_masked*255)
    obs_map = np.absolute(np.float32(threshed)-1)
    
    Rover.vision_image[:, :, 2] = threshed*255
    Rover.vision_image[:, :, 0] = obs_map*255
    
    xpix, ypix = rover_coords(threshed_masked)
    world_size = Rover.worldmap.shape[0]
    scale = 2 * dst_size
    x_world, y_world = pix_to_world(xpix, ypix, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size, scale)
    
    obsxpix, obsypix = rover_coords(obs_map)
    obs_x_world, obs_y_world = pix_to_world(obsxpix, obsypix, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size, scale)

    if abs(Rover.pitch) < 1 and abs(Rover.roll) <1:
        Rover.worldmap[y_world, x_world, 2] += 10
        Rover.worldmap[obs_y_world, obs_x_world, 0] += 1

    dist, angles = to_polar_coords(xpix, ypix)

    Rover.nav_angles = angles
    rock_map = get_rocks(warped)
    if rock_map.any():
        rock_x, rock_y = rover_coords(rock_map)
        rock_x_world, rock_y_world = pix_to_world(rock_x, rock_y, Rover.pos[0], Rover.pos[1], Rover.yaw, world_size, scale)
        rock_dist, rock_angel = to_polar_coords(rock_x, rock_y)
        rock_idx = np.argmin(rock_dist)
        rock_xcen = rock_x_world[rock_idx]
        rock_y_cen = rock_y_world[rock_idx]
        Rover.worldmap[rock_y_cen, rock_xcen, 1] = 255
        Rover.vision_image[:, :, 1] = rock_map * 255
    else:
        Rover.vision_image[:, :, 1] = 0
   
    if (Rover.debug):
        for i, image in enumerate(debuggingPipe):
            BGRimage = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) 
            cv2.imshow(str(i+1), BGRimage)
        cv2.waitKey(15)
    
    return Rover