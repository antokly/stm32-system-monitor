/*
 * uart_protocol.h
 *
 *  Created on: 15 oct. 2026
 *      Author: Anton
 */

#ifndef INC_UART_PROTOCOL_H_
#define INC_UART_PROTOCOL_H_

#include <stdbool.h>
#include "stm32l4xx_hal.h"

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart);

bool get_frame_ready_flag(void);
uint8_t get_frame_cmd_id(void);
uint8_t get_frame_len(void);
uint8_t* get_frame_payload(void);
void set_frame_ready_flag(bool value);

#endif /* INC_UART_PROTOCOL_H_ */
