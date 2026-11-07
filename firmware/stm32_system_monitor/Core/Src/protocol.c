/*
 * uart_protocol.c
 *
 *  Created on: 15 oct. 2026
 *      Author: antokly
 */
#include "protocol.h"
#include "actions.h"
#include "crc.h"
#include <string.h>

void req_parser_init(req_parser_t *p)
{
    p->state = REQ_WAIT_SOF;
    p->index = 0U;
    p->crc   = 0U;
}

bool req_parse_byte(req_parser_t *p, uint8_t byte)
{
    switch (p->state) {
    case REQ_WAIT_SOF:
        if (byte == REQ_SOF) {
            p->crc = 0U;
            p->state = REQ_WAIT_CMD;
        }
        break;

    case REQ_WAIT_CMD:
        p->req.cmd = byte;
        p->crc = crc8_compute(p->crc, byte);
        p->state = REQ_WAIT_LEN;
        break;

    case REQ_WAIT_LEN:
        if (byte > REQ_MAX_PAYLOAD) { // longueur aberrante : on resynchronise
            p->state = REQ_WAIT_SOF;
            break;
        }
        p->req.len = byte;
        p->index = 0U;
        p->crc = crc8_compute(p->crc, byte);
        p->state = (byte == 0U) ? REQ_WAIT_CRC : REQ_WAIT_PAYLOAD;
        break;

    case REQ_WAIT_PAYLOAD:
        p->req.payload[p->index++] = byte;
        p->crc = crc8_compute(p->crc, byte);
        if (p->index >= p->req.len) {
            p->state = REQ_WAIT_CRC;
        }
        break;

    case REQ_WAIT_CRC:
        p->state = REQ_WAIT_SOF;
        return (byte == p->crc); // true = trame valide dans p->req

    default:
        p->state = REQ_WAIT_SOF;
        break;
    }
    return false;
}

size_t req_encode(uint8_t cmd, const uint8_t *payload, uint8_t len, uint8_t *out)
{
    if (len > REQ_MAX_PAYLOAD) {
        return 0U;
    }
    size_t pos = 0U;
    out[pos++] = REQ_SOF;
    out[pos++] = cmd;
    out[pos++] = len;
    if (len > 0U && payload != NULL) {
        memcpy(&out[pos], payload, len);
        pos += len;
    }
    out[pos] = req_crc8(&out[1], 2U + len); // CRC sur CMD + LEN + PAYLOAD
    pos++;
    return pos;
}

/* requests treatments */
size_t req_handle(const req_t *req, uint8_t *out)
{
    uint8_t resp[REQ_MAX_PAYLOAD];
    uint8_t n = 0U;
    uint8_t err = 0U;

    switch (req->cmd) {
    case CMD_PING:
        break;

    case CMD_GET_TEMP: {
        float t = board_read_temp();
        memcpy(resp, &t, sizeof t);
        n = (uint8_t)sizeof t;
        break;
    }

    case CMD_GET_VBAT: {
        float v = board_read_vbat();
        memcpy(resp, &v, sizeof v);
        n = (uint8_t)sizeof v;
        break;
    }

    case CMD_GET_ADC: {
        uint16_t adc[3];
        board_read_adc(adc);
        memcpy(resp, adc, sizeof adc);
        n = (uint8_t)sizeof adc;
        break;
    }

    case CMD_SET_PWM:
        if (req->len != 2U) {
            err = ERR_BAD_LENGTH;
        } else if (!board_set_pwm(req->payload[0], req->payload[1])) {
            err = ERR_BAD_PARAM;
        }
        break;

    case CMD_GET_ALL: {
        float t = board_read_temp();
        float v = board_read_vbat();
        uint16_t adc[3];
        board_read_adc(adc);
        memcpy(&resp[0], &t, 4);
        memcpy(&resp[4], &v, 4);
        memcpy(&resp[8], adc, 6);
        n = 14U;
        break;
    }

    default:
        err = ERR_UNKNOWN_CMD;
        break;
    }

    if (err != 0U) {
        const uint8_t e[2] = { req->cmd, err };
        return req_encode(CMD_ERROR, e, 2U, out);
    }
    return req_encode(req->cmd, resp, n, out);
}

