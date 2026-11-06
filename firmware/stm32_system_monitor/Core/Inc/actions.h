/*
 * actions.h
 *
 *  Created on: 28 oct. 2026
 *      Author: Anton
 */

#ifndef INC_ACTIONS_H_
#define INC_ACTIONS_H_
#include <stdint.h>
#include <stdbool.h>

uint32_t read_temperature(void);

void set_pwm(uint8_t param1, uint8_t param2);

#endif /* INC_ACTIONS_H_ */
