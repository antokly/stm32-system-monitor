/*
 * actions.h
 *
 *  Created on: 28 oct. 2026
 *      Author: antokly
 */

#ifndef INC_ACTIONS_H_
#define INC_ACTIONS_H_
#include <stdint.h>
#include <stdbool.h>

float board_read_temp(void);
float board_read_vbat(void);
void  board_read_adc(uint16_t adc[3]);
bool  board_set_pwm(uint8_t channel, uint8_t duty_percent);

#endif /* INC_ACTIONS_H_ */
