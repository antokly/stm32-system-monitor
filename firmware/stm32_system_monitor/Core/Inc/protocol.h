/*
 * protocol.h
 *
 *  Created on: 15 oct. 2026
 *      Author: Anton
 */

#ifndef INC_PROTOCOL_H_
#define INC_PROTOCOL_H_

#define FRAME_SOF   0xAA
#define FRAME_EOF   0x55
#define MAX_PAYLOAD 28   // trame totale max = 32B (SOF+CMD+LEN+28+CRC+EOF)

typedef enum {
    CMD_PING     = 0x01,
    CMD_GET_TEMP = 0x02,
    CMD_GET_VBAT = 0x03,
    CMD_GET_ADC  = 0x05,
    CMD_SET_PWM  = 0x09,
    CMD_GET_ALL  = 0x0A,
    CMD_ERROR    = 0xFF
} cmd_id_t;


#endif /* INC_PROTOCOL_H_ */
