/*
 * crc.c
 *
 *  Created on: 15 oct. 2026
 *      Author: antokly
 */
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>

static const uint8_t crc8_table[256] = {
    // Table CRC8-CCITT
};

uint8_t crc8_compute(uint8_t crc, uint8_t byte)
{
    crc ^= byte;
    for (uint8_t bit = 0; bit < 8U; bit++) {
        crc = (crc & 0x80U) ? (uint8_t)((crc << 1) ^ 0x07U) : (uint8_t)(crc << 1);
    }
    return crc;
}

uint8_t req_crc8(const uint8_t *data, size_t len)
{
    uint8_t crc = 0U;
    while (len--) {
        crc = crc8_compute(crc, *data++);
    }
    return crc;
}
