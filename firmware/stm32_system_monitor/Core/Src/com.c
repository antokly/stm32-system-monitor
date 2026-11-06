/*
 * com.c : Communication UART Application
 *
 *  Created on: 15 oct. 2026
 *      Author: Anton
 */
#include "protocol.h"
#include "uart_protocol.h"
#include "main.h"
#include "actions.h"
#include <string.h>

void protocol_process(void)
{
    if (!get_frame_ready_flag()) return;

    uint8_t cmd_id = get_frame_cmd_id();
    uint8_t len = get_frame_len();
    uint8_t payload[MAX_PAYLOAD];
    memcpy(payload, get_frame_payload(), len);

    set_frame_ready_flag(false); // libère le buffer de réception dès la copie faite

    switch (cmd_id)
    {
        case CMD_PING:
            send_frame(CMD_PING, NULL, 0);
            break;

        case CMD_GET_TEMP:
        {
            float t = read_temperature();
            send_frame(CMD_GET_TEMP, (uint8_t*)&t, sizeof(t));
            break;
        }

        case CMD_SET_PWM:
        {
            if (len < 2) { send_error(cmd_id); break; }
            set_pwm(payload[0], payload[1]);
            send_frame(CMD_SET_PWM, NULL, 0);
            break;
        }

        default:
            send_error(cmd_id);
            break;
    }
}
