/*
 * action.c
 *
 *  Created on: 28 oct. 2026
 *      Author: antokly
 */
#include "actions.h"

__attribute__((weak)) float board_read_temp(void) { return 25.0f; }
__attribute__((weak)) float board_read_vbat(void) { return 12.0f; }
__attribute__((weak)) void  board_read_adc(uint16_t adc[3]) { adc[0] = 0; adc[1] = 0; adc[2] = 0; }
__attribute__((weak)) bool  board_set_pwm(uint8_t ch, uint8_t duty) { (void)ch; return duty <= 100U; }
