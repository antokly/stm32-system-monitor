/*
 * com.c : Communication UART
 *
 *  Created on: 15 oct. 2026
 *      Author: antokly
 */
#include "com.h"
#include "protocol.h"
#include "main.h"

#define RX_TIMEOUT_MS   100U // reception timeout

static req_parser_t parser;
static uint8_t rx_byte;
static uint32_t last_rx_tick;
static req_t pending; // last frame waiting decode treatment
static volatile bool pending_ready;

/* relaunch if HAL stopped */
static void rx_rearm_if_stopped(void)
{
    if ((&huart1)->RxState == HAL_UART_STATE_READY) {
        __HAL_UART_CLEAR_FLAG(&huart1, UART_CLEAR_OREF | UART_CLEAR_FEF |
                                        UART_CLEAR_NEF  | UART_CLEAR_PEF);
        req_parser_init(&parser);
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
    }
}

void com_init(void)
{
    req_parser_init(&parser);
    HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
}

void com_process(void)
{
    rx_rearm_if_stopped();

    if (!pending_ready) {
        return;
    }
    req_t input_request = pending; // copy and free
    pending_ready = false;

    uint8_t output_tx_buf[REQ_MAX_FRAME];
    size_t len = req_handle(&input_request, output_tx_buf);
    if (len > 0U) {
        HAL_UART_Transmit(&huart1, output_tx_buf, (uint16_t)len, 100U);
    }
}

void HAL_UART_RxCpltCallback(UART_HandleTypeDef *huart)
{
    if (huart == &huart1) {
        uint32_t now = HAL_GetTick();
        if ((now - last_rx_tick) > RX_TIMEOUT_MS) {
            req_parser_init(&parser); // clean frame
        }
        last_rx_tick = now;

        if (req_parse_byte(&parser, rx_byte) && !pending_ready) {
            pending = parser.req;
            pending_ready = true;
        }
        HAL_UART_Receive_IT(&huart1, &rx_byte, 1U);
    }
}

/* UART Error (overrun, bruit...) : clean frame
 * reception relaunch is done in rx_rearm_if_stopped() into com_process().
 * */
void HAL_UART_ErrorCallback(UART_HandleTypeDef *huart)
{
    if (huart == &huart1) {
        req_parser_init(&parser);
    }
}
