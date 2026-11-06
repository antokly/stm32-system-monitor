/*
 * uart_protocol.c
 *
 *  Created on: 15 oct. 2026
 *      Author: Anton
 */
#include <stdint.h>
#include <string.h>
#include <stdbool.h>
#include "protocol.h"
#include "stm32l4xx_hal.h"
#include "crc.h"

typedef enum {
    RX_WAIT_SOF,
    RX_WAIT_CMDID,
    RX_WAIT_LEN,
    RX_WAIT_PAYLOAD,
    RX_WAIT_CRC,
    RX_WAIT_EOF
} rx_state_t;

typedef struct {
    rx_state_t state;
    uint8_t cmd_id;
    uint8_t len;
    uint8_t payload[MAX_PAYLOAD];
    uint8_t idx;
    uint8_t crc_calc;   // CRC calculé au fil de la réception
} rx_ctx_t;

static rx_ctx_t rx_ctx = { .state = RX_WAIT_SOF };
static uint8_t rx_byte;

// Buffer "trame complète" prêt à être traité en dehors de l'IRQ
static volatile bool frame_ready_flag = false;
static uint8_t frame_cmd_id;
static uint8_t frame_len;
static uint8_t frame_payload[MAX_PAYLOAD];

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart->Instance != USART1) return;

    uint8_t b = rx_byte;

    switch (rx_ctx.state)
    {
        case RX_WAIT_SOF:
            if (b == FRAME_SOF) {
                rx_ctx.state = RX_WAIT_CMDID;
            }
            break;

        case RX_WAIT_CMDID:
            rx_ctx.cmd_id = b;
            rx_ctx.state = RX_WAIT_LEN;
            break;

        case RX_WAIT_LEN:
            if (b > MAX_PAYLOAD) {
                rx_ctx.state = RX_WAIT_SOF;  // trame invalide, on reset direct
                break;
            }
            rx_ctx.len = b;
            rx_ctx.idx = 0;
            rx_ctx.state = (b == 0) ? RX_WAIT_CRC : RX_WAIT_PAYLOAD;
            break;

        case RX_WAIT_PAYLOAD:
            rx_ctx.payload[rx_ctx.idx++] = b;
            if (rx_ctx.idx >= rx_ctx.len)
                rx_ctx.state = RX_WAIT_CRC;
            break;

        case RX_WAIT_CRC:
            rx_ctx.crc_calc = b;  // on stocke, vérif faite avant EOF
            rx_ctx.state = RX_WAIT_EOF;
            break;

        case RX_WAIT_EOF:
            if (b == FRAME_EOF && !frame_ready_flag)
            {
                // Vérification CRC : recalcul sur cmd_id+len+payload
                uint8_t buf[2 + MAX_PAYLOAD];
                buf[0] = rx_ctx.cmd_id;
                buf[1] = rx_ctx.len;
                memcpy(&buf[2], rx_ctx.payload, rx_ctx.len);

                if (crc8(buf, 2 + rx_ctx.len) == rx_ctx.crc_calc)
                {
                    // Trame valide -> copie dans le buffer "prêt"
                    frame_cmd_id = rx_ctx.cmd_id;
                    frame_len = rx_ctx.len;
                    memcpy(frame_payload, rx_ctx.payload, rx_ctx.len);
                    frame_ready_flag = true;
                }
                // sinon : trame silencieusement rejetée (CRC KO)
            }
            rx_ctx.state = RX_WAIT_SOF;
            break;
    }

    HAL_UART_Receive_IT(huart, &rx_byte, 1); // réarme pour le prochain octet
}

bool get_frame_ready_flag(void)
{
	return frame_ready_flag;
}

uint8_t get_frame_cmd_id(void)
{
	return frame_cmd_id;
}

uint8_t get_frame_len(void)
{
	return frame_len;
}

uint8_t* get_frame_payload(void)
{
	return frame_payload;
}

void set_frame_ready_flag(bool value)
{
	frame_ready_flag = value;
}
