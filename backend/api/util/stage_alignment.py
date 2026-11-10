import cv2
import numpy as np
import matplotlib.pyplot as plt
def feature_match(img_ref, img_tar, save_path=None):    
    """opencv based feature matching"""
    MAX_FEATURES = 500 
    GOOD_MATCH_PERCENT = 0.99

    # Detect ORB features
    orb = cv2.ORB_create(MAX_FEATURES)
    #just in case normalise
    img_ref = cv2.normalize(img_ref,None,0,255,cv2.NORM_MINMAX).astype(np.uint8)
    img_tar = cv2.normalize(img_tar,None,0,255,cv2.NORM_MINMAX).astype(np.uint8)
    print(img_tar.shape, img_tar.dtype, img_tar.max(),img_tar.min())

    # keypoints1 = query image (ref), keypoints2 = train image (target)
    keypoints1, descriptors1 = orb.detectAndCompute(img_ref, None)
    keypoints2, descriptors2 = orb.detectAndCompute(img_tar, None)

    #Match features
    matcher = cv2.DescriptorMatcher_create(cv2.DESCRIPTOR_MATCHER_BRUTEFORCE_HAMMING)
    matches = matcher.match(descriptors1, descriptors2, None)
    matches = sorted(matches, key=lambda x: x.distance)

    # Remove not so good matches
    numGoodMatches = int(len(matches) * GOOD_MATCH_PERCENT)
    matches = matches[:numGoodMatches]

    if save_path:
        print("plotting features")
        imMatches = cv2.drawMatches(img_ref, keypoints1, img_tar, keypoints2, matches, None)
        plt.figure(figsize=(10,5))
        plt.imshow(imMatches)
        plt.savefig(rf"{save_path}/feature_match.png", dpi=150)
        
    # Extract location of good matches
    points_query = np.zeros((len(matches), 2), dtype=np.float32)
    points_train = np.zeros((len(matches), 2), dtype=np.float32)
    
    for i, match in enumerate(matches):
        points_query[i, :] = keypoints1[match.queryIdx].pt # Points in Ref
        points_train[i, :] = keypoints2[match.trainIdx].pt # Points in Target
        
    M, _ = cv2.estimateAffinePartial2D(points_query, points_train)

    return M #points_query, points_train

def get_transformed_corners(box, M):
    x, y, w, h = box
    corners = np.array([
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h]
    ], dtype=np.float32)
    corners = np.array([corners])
    transformed_corners = cv2.transform(corners, M)
    return transformed_corners

    
def get_center_offset(img_ref, img_tar, save_path = None):
    """
    Feature match img_ref against img_tar and find where img_ref's center lands in img_tar once mapped through
    the estimated affine transform, relative to img_tar's own center.

    Returns (dx, dy) in img_tar pixels, or None if matching failed.

    """        
    M = feature_match(img_ref, img_tar, save_path=save_path)
    if M is None:
        return None
    print(M)
    ref_h, ref_w = img_ref.shape[:2]
    tar_h, tar_w = img_tar.shape[:2]

    ref_center = np.array([[[ref_w / 2, ref_h / 2]]], dtype=np.float32)
    mapped_center = cv2.transform(ref_center, M)[0, 0]
    tar_center = np.array([tar_w / 2, tar_h / 2])
    print(mapped_center)
    print(tar_center)
    px_shift = mapped_center - tar_center
    return px_shift*-1 # NOTE TODO CONFIRM DIRECTIONS!