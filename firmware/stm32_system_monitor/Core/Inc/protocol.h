/*
 * protocol.h
 *
 *  Created on: 15 oct. 2026
 *      Author: antokly
 */

#ifndef INC_PROTOCOL_H_
#define INC_PROTOCOL_H_

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/*
 * Trame :  [SOF 0xA5] [CMD] [LEN] [PAYLOAD (LEN octets)] [CRC8]
 * CRC8   :  CRC-8/SMBUS (poly 0x07, init 0x00, sans reflexion, sans XOR final)
 *           calculé sur CMD + LEN + PAYLOAD (le SOF n'est pas protégé)
 * Les valeurs multi-octets du payload sont en little-endian (natif Cortex-M).
 */
#define REQ_SOF          0xA5U
#define REQ_MAX_PAYLOAD  32U
#define REQ_HEADER_SIZE  3U     /* SOF + CMD + LEN */
#define REQ_CRC_SIZE     1U
#define REQ_MAX_FRAME    (REQ_HEADER_SIZE + REQ_MAX_PAYLOAD + REQ_CRC_SIZE)

typedef enum {
    CMD_PING     = 0x01,
    CMD_GET_TEMP = 0x02,   /* rép : float32 (°C)                        */
    CMD_GET_VBAT = 0x03,   /* rép : float32 (V)                         */
    CMD_GET_ADC  = 0x05,   /* rép : uint16 x3                           */
    CMD_SET_PWM  = 0x09,   /* req : uint8 canal, uint8 duty (0-100)     */
    CMD_GET_ALL  = 0x0A,   /* rép : float32 temp, float32 vbat, uint16 adc[3] */
    CMD_ERROR    = 0xFF    /* rép : uint8 cmd fautive, uint8 code erreur */
} cmd_id_t;

typedef enum {
    ERR_UNKNOWN_CMD = 0x01,
    ERR_BAD_LENGTH  = 0x02,
    ERR_BAD_PARAM   = 0x03
} err_code_t;

/* Paquet décodé */
typedef struct {
    uint8_t cmd;
    uint8_t len;
    uint8_t payload[REQ_MAX_PAYLOAD];
} req_t;

/* Parseur */
typedef enum {
    REQ_WAIT_SOF,
    REQ_WAIT_CMD,
    REQ_WAIT_LEN,
    REQ_WAIT_PAYLOAD,
    REQ_WAIT_CRC
} req_state_t;

typedef struct {
    req_state_t state;
    uint8_t     index;
    uint8_t     crc;      /* CRC calculé au fil de l'eau */
    req_t       req;      /* valide quand req_parse_byte() retourne true */
} req_parser_t;

uint8_t req_crc8(const uint8_t *data, size_t len);
void    req_parser_init(req_parser_t *p);
bool    req_parse_byte(req_parser_t *p, uint8_t byte);

/* Encode une trame dans out (>= REQ_MAX_FRAME). Retourne la longueur, 0 si erreur. */
size_t  req_encode(uint8_t cmd, const uint8_t *payload, uint8_t len, uint8_t *out);

/* Traite une requête, écrit la trame de réponse dans out. Retourne sa longueur. */
size_t  req_handle(const req_t *req, uint8_t *out);

#endif /* INC_PROTOCOL_H_ */
