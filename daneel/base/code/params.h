/*
 * params.h
 *
 *  Created on: 16 nov. 2017
 *      Author: fabien
 */

#ifndef PARAMS_H_
#define PARAMS_H_
#include "Arduino.h"
#include "arm_math.h"

//#define SIMULATOR

const int LED_PIN = 13;

const float ODOMETRY_PERIOD = 0.01;
const float CONTROL_PERIOD = 0.05;
const float POS_REPORT_PERIOD = 0.05;
const float IO_REPORT_PERIOD = 0.5;

const float32_t DRIFTING_THRESHOLD = 20;

/* BEGIN -----------------Motors & Odometry-------------------------- */

const int MOT1_PWM = 5;
const int MOT1_DIR = 6;
const int MOT1_ENCA = 24;
const int MOT1_ENCB = 25;

const int MOT2_PWM = 7;
const int MOT2_DIR = 8;
const int MOT2_ENCA = 26;
const int MOT2_ENCB = 27;

const int POS_ENC1A = 3;	//PTA12		ALT7: FTM1_QD_PHA
const int POS_ENC1B = 4;	//PTA13		ALT7: FTM1_QD_PHB

const int POS_ENC2A = 29;	//PTB18		ALT6: FTM2_QD_PHA
const int POS_ENC2B = 30;	//PTB19		ALT6: FTM2_QD_PHB

const float PWM_FREQUENCY = 915.527;
const int PWM_RESOLUTION = 8;
const int PWM_MAX = pow(2, PWM_RESOLUTION) - 5;

const float32_t INC_PER_MM = 9.866663789678743;
const float32_t WHEELBASE = 154.84329099722402;		//todo change this

const float32_t INC_PER_MM_CODING_WHEELS = 27.653438736797984;
const float32_t WHEELBASE_CODING_WHEELS = 289.88388523039015;



/* END ------------------- Motors & Odometry --------------------------*/

/* BEGIN ----------------------- HMI ----------------------------------*/
const int LED_RED = 23;
const int LED_GREEN = 22;
const int LED_BLUE = 21;

const int BUTTON1 = 15;
const int CORD = 34;
const int BUTTON2 = 16;

const int DATA_433 = 33;
const int SERVO = 14;
const int LIDAR_SPEED = 20;

const int AUX1 = 35;
const int AUX2 = 36;
const int AUX3 = 37;
const int AUX4 = 9;
const int AUX5 = 10;
const int AUX6 = 11;
const int AUX7 = 12;

const int UART4_RX = 31;
const int UART4_TX = 32;

const int SDA0 = 18;
const int SCL0 = 19;


const int VL6180X_LEFT = AUX1;
const int VL6180X_CENTER = AUX2;
const int VL6180X_RIGHT = AUX3;

/* END ------------------------- HMI ----------------------------------*/

/* BEGIN ----------------------- IOs ----------------------------------*/
const int RASPI_COMMUNICATION_BAUDRATE = 115200;
//const int DYNAMIXEL_CONTROL = 35;
const int SCORE_DISPLAY_DIO = 38;
const int SCORE_DISPLAY_CLK = 39;
const int BAT_SIG = A3;
const int BAT_POW = A22;
/* END ------------------------- IOs ----------------------------------*/

const int LIDAR_BASE_PWM = 244;

const unsigned int TIME_SPEED_FAILSAFE = 1000;

#endif /* PARAMS_H_ */
