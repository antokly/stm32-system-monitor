/*
 * crc.h
 *
 *  Created on: 15 oct. 2026
 *      Author: antokly
 */

#ifndef INC_CRC_H_
#define INC_CRC_H_

uint8_t crc8_compute(uint8_t crc, uint8_t byte);
uint8_t req_crc8(const uint8_t *data, size_t len);

#endif /* INC_CRC_H_ */
