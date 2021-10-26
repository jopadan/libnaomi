#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "common.h"
#include "message.h"
#include "packet.h"

#define MAX_MESSAGE_LENGTH 0xFFFF
#define MESSAGE_HEADER_LENGTH 8
#define MAX_MESSAGE_DATA_LENGTH (MAX_PACKET_LENGTH - MESSAGE_HEADER_LENGTH)
#define MESSAGE_ID_LOC 0
#define MESSAGE_SEQ_LOC 2
#define MESSAGE_LEN_LOC 4
#define MESSAGE_LOC_LOC 6
#define MESSAGE_DATA_LOC 8

int message_send(uint16_t type, void * data, unsigned int length)
{
    uint8_t buffer[MAX_PACKET_LENGTH];
    static uint16_t sequence = 1;

    if (length > MAX_MESSAGE_LENGTH)
    {
        return -3;
    }

    // We always want to run this loop at least one time, so we can send
    // packets of 0 bytes in length.
    for (unsigned int loc = 0; (loc == 0 || loc < length); loc += MAX_MESSAGE_DATA_LENGTH)
    {
        unsigned int packet_len = length - loc;
        if (packet_len > MAX_MESSAGE_DATA_LENGTH)
        {
            packet_len = MAX_MESSAGE_DATA_LENGTH;
        }

        // Set up packet type in header.
        uint16_t tmp = type;
        memcpy(&buffer[MESSAGE_ID_LOC], &tmp, 2);

        // Set up sequence number in header.
        memcpy(&buffer[MESSAGE_SEQ_LOC], &sequence, 2);

        // Set up packet length in header.
        tmp = length;
        memcpy(&buffer[MESSAGE_LEN_LOC], &tmp, 2);

        // Set up current packet location in header.
        tmp = loc;
        memcpy(&buffer[MESSAGE_LOC_LOC], &tmp, 2);

        if (packet_len > 0)
        {
            // Finally, copy the data in.
            memcpy(&buffer[MESSAGE_DATA_LOC], ((uint8_t *)data) + loc, packet_len);
        }

        // Now, send the packet.
        if (packetlib_send(buffer, packet_len + MESSAGE_HEADER_LENGTH) != 0)
        {
            return -4;
        }
    }

    // We finished this packet, set the sequence number to something else for
    // the next packet.
    sequence ++;
    if (sequence == 0)
    {
        // Don't want sequence ID 0 for reassembly purposes.
        sequence = 1;
    }

    return 0;
}

int message_recv(uint16_t *type, void ** data, unsigned int *length)
{
    // Figure out if there is a packet worth assembling. This is a really gross,
    // inefficient algorithm, but whatever its good enough for now.
    uint8_t *reassembled_data = 0;
    int success = -5;
    uint16_t seen_packet_sequences[MAX_OUTSTANDING_PACKETS];
    uint8_t *seen_positions[MAX_OUTSTANDING_PACKETS];
    uint16_t seen_packet_lengths[MAX_OUTSTANDING_PACKETS];
    memset(seen_packet_sequences, 0, sizeof(uint16_t) * MAX_OUTSTANDING_PACKETS);
    memset(seen_positions, 0, sizeof(uint8_t *) * MAX_OUTSTANDING_PACKETS);
    memset(seen_packet_lengths, 0, sizeof(uint16_t) * MAX_OUTSTANDING_PACKETS);

    for (unsigned int pkt = 0; pkt < MAX_OUTSTANDING_PACKETS; pkt++)
    {
        // Grab the potential packet we could receive.
        unsigned int pkt_length = 0;
        uint8_t *pkt_data = packetlib_peek(pkt, &pkt_length);
        if (pkt_data == 0)
        {
            // No data for this packet.
            continue;
        }
        if (pkt_length < MESSAGE_HEADER_LENGTH)
        {
            // Toss bogus packet.
            packetlib_discard(pkt);
            continue;
        }

        // Grab the sequence number from this packet.
        uint16_t sequence;
        int index = -1;
        memcpy(&sequence, &pkt_data[MESSAGE_SEQ_LOC], 2);

        if (sequence == 0)
        {
            // Toss bogus packet.
            packetlib_discard(pkt);
            continue;
        }

        // Grab the length and needed total packets for this packet.
        uint16_t msg_length;
        memcpy(&msg_length, &pkt_data[MESSAGE_LEN_LOC], 2);
        unsigned int num_packets_needed = (msg_length + (MAX_MESSAGE_DATA_LENGTH - 1)) / MAX_MESSAGE_DATA_LENGTH;

        // Find the positions data for this sequence.
        for (unsigned int i = 0; i < MAX_OUTSTANDING_PACKETS; i++)
        {
            if (seen_packet_sequences[i] == sequence)
            {
                index = i;
                break;
            }
            if (seen_packet_sequences[i] == 0)
            {
                // The index doesn't exist, lets create it.
                index = i;

                // Calculate how many parts of the message we need to see.
                seen_packet_sequences[index] = sequence;
                seen_packet_lengths[index] = msg_length;
                if (num_packets_needed > 0)
                {
                    seen_positions[index] = malloc(num_packets_needed);
                    memset(seen_positions[index], 0, num_packets_needed);
                }
                break;
            }
        }

        if (num_packets_needed > 0 && index >= 0)
        {
            // Now, mark the particular portion of this packet as present.
            uint16_t location;
            memcpy(&location, &pkt_data[MESSAGE_LOC_LOC], 2);
            seen_positions[index][location / MAX_MESSAGE_DATA_LENGTH] = 1;
        }
    }

    // Now that we've gathered up which packets we have, see if any packets
    // we care about are fully received.
    for (unsigned int index = 0; index < MAX_OUTSTANDING_PACKETS; index++)
    {
        if (seen_packet_sequences[index] == 0)
        {
            // We ran out of packet sequences we're tracking.
            break;
        }

        unsigned int num_packets_needed = (seen_packet_lengths[index] + (MAX_MESSAGE_DATA_LENGTH - 1)) / MAX_MESSAGE_DATA_LENGTH;
        int ready = 1;

        for (unsigned int i = 0; i < num_packets_needed; i++)
        {
            if (!seen_positions[index][i])
            {
                // This packet is not ready.
                ready = 0;
                break;
            }
        }

        if (ready)
        {
            // This packet is ready!
            if (seen_packet_lengths[index] > 0)
            {
                reassembled_data = malloc(seen_packet_lengths[index]);
            }
            *data = reassembled_data;
            *length = seen_packet_lengths[index];

            for (unsigned int pkt = 0; pkt < MAX_OUTSTANDING_PACKETS; pkt++)
            {
                // Grab the potential packet we could receive.
                unsigned int pkt_length = 0;
                uint8_t *pkt_data = packetlib_peek(pkt, &pkt_length);
                if (pkt_data == 0 || pkt_length < MESSAGE_HEADER_LENGTH)
                {
                    // No data for this packet.
                    continue;
                }

                // Grab the sequence number from this packet.
                uint16_t sequence;
                memcpy(&sequence, &pkt_data[MESSAGE_SEQ_LOC], 2);

                if (sequence != seen_packet_sequences[index])
                {
                    // This packet is not one of the ones we're after.
                    continue;
                }

                // Grab the type from this packet. This is inefficient since we
                // only need to do it once, but whatever. Its two whole bytes and
                // this entire reassembly algorithm could use work.
                memcpy(type, &pkt_data[MESSAGE_ID_LOC], 2);

                if (seen_packet_lengths[index] > 0)
                {
                    // Grab the location from this packet, so we can copy it into
                    // the right spot in the destination.
                    uint16_t location;
                    memcpy(&location, &pkt_data[MESSAGE_LOC_LOC], 2);

                    // Actually copy it.
                    memcpy(reassembled_data + location, &pkt_data[MESSAGE_DATA_LOC], pkt_length - MESSAGE_HEADER_LENGTH);
                }

                // We don't need this packet anymore, since we received it.
                packetlib_discard(pkt);
            }

            // We finished assembling the packet, lets return it!
            success = 0;
            break;
        }
    }

    // Need to free a bunch of stuff.
    for (unsigned int index = 0; index < MAX_OUTSTANDING_PACKETS; index++)
    {
        if (seen_positions[index])
        {
            free(seen_positions[index]);
        }
    }

    // Return the possibly reassembled packet.
    return success;
}
