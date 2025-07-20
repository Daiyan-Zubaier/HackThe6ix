#ifndef CAMERA_CONFIG_H
#define CAMERA_CONFIG_H

#include "esp_camera.h"

// Function declarations
void camera_configuration(camera_config_t &config);
void set_camera(camera_config_t &config);
void camera_start(camera_config_t &config);
void setupLedFlash(int pin);

#endif