/*
 * crc.c
 *
 *  Created on: 15 oct. 2026
 *      Author: Anton
 */
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>

static const uint8_t crc8_table[256] = {
    // Table CRC8-CCITT poly 0x07 — génère-la une fois avec un script,
    // je te la fournis si besoin, ou calcul direct sans table (plus lent mais plus simple) :
};

uint8_t crc8(const uint8_t *data, uint8_t len)
{
    uint8_t crc = 0x00;
    for (uint8_t i = 0; i < len; i++)
    {
        crc ^= data[i];
        for (uint8_t b = 0; b < 8; b++)
            crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : (crc << 1);
    }
    return crc;
}

