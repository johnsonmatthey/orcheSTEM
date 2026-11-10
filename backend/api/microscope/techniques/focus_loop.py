# ED 05-02-2026 
# ZN 05-02-2026 for fixing vars
# Adapted from Automated-Data-Collection/_focus.py

import numpy as np
import matplotlib.pyplot as plt
from util import data_io 
import os    
from pathlib import Path

def plot_coarse_range(coarse_steps, coarse_var, fine_steps, fine_var, chosen_location = None, return_fig = True):
    fig, ax = plt.subplots()
    ax.scatter(coarse_steps, coarse_var, label="Coarse", marker="o", color = 'b')
    ax.scatter(fine_steps, fine_var, label="Fine", marker="x", color = 'r')

    if chosen_location:
        ax.plot(chosen_location[0], chosen_location[1], "g*", label="point of interest")
        ax.annotate("CHOSEN", xy=chosen_location, xytext=(10, 6), textcoords='offset points', ha='right', va='bottom', color='green', fontsize=15)

    # annotate each marker with its 1-based index (top-right)
    for i, (x, y) in enumerate(zip(coarse_steps, coarse_var), 1):
        ax.annotate(str(i), xy=(x, y), xytext=(6, 6), textcoords='offset points', ha='left', va='bottom', fontsize=10)

    for i, (x, y) in enumerate(zip(fine_steps, fine_var), 1):
        ax.annotate(str(i), xy=(x, y), xytext=(6, 6), textcoords='offset points', ha='left', va='bottom', fontsize=10)
    ax.set_xlabel("OLf val", fontsize = 14)
    ax.set_ylabel("Normalised Variance", fontsize = 14)
    ax.legend()
    if return_fig:
        return fig
    else:
        plt.show()

def _norm_var(img_data: np.ndarray) -> float:
    """Calculates normalized variance: (std / mean)^2."""
    mean = np.mean(img_data)
    std = np.std(img_data)
    return (std ** 2) / (mean ** 2) if mean != 0 else 0

def _norm_var_quad(img_data: np.ndarray, no_quad: int = 4) -> np.ndarray:
    """Calculates normalized variance: (std / mean)^2. in a 4x4 grid of the image"""
    box_size = np.floor(np.shape(img_data)[0]/no_quad).astype(int)
    mean_matrix = np.zeros((no_quad,no_quad))
    std_matrix = np.zeros((no_quad,no_quad))
    var_matrix = np.zeros((no_quad,no_quad))
    for i in np.arange(no_quad-1):
        for j in np.arange(no_quad-1):
            mean_matrix[i,j] = np.mean(img_data[box_size*(i):box_size*(i+1),box_size*(j):box_size*(j+1)])
            std_matrix[i,j] = np.std(img_data[box_size*(i):box_size*(i+1),box_size*(j):box_size*(j+1)])
            if mean_matrix[i,j] !=0:
                var_matrix[i,j] = (std_matrix[i,j] **2) / (mean_matrix[i,j] **2)
            else:
                var_matrix[i,j]=0
    return var_matrix

def _parabolic_fit(x_points, y_points):
    """Fits a parabola to 3 points and returns the vertex (x_max, y_max)."""
    if len(x_points) < 3:
        return x_points[np.argmax(y_points)], np.max(y_points)
    
    # Fit y = ax^2 + bx + c
    coeffs = np.polyfit(x_points, y_points, 2)
    a, b, c = coeffs
    
    # Check if it's a peak (a < 0) or valley (a > 0)
    if a >= 0: 
        # If it convex (valley) or flat, return max data point
        idx = np.argmax(y_points)
        return x_points[idx], y_points[idx]
    
    # Vertex x = -b / 2a
    vertex_x = -b / (2 * a)
    vertex_y = a * vertex_x**2 + b * vertex_x + c
    return vertex_x, vertex_y
