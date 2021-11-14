#ifndef __HOLLY_H
#define __HOLLY_H

// Internal to the HOLLY itself.
#define HOLLY_INTERNAL_IRQ_STATUS *((volatile uint32_t *)0xA05F6900)
#define HOLLY_INTERNAL_IRQ_2_MASK *((volatile uint32_t *)0xA05F6910)
#define HOLLY_INTERNAL_IRQ_4_MASK *((volatile uint32_t *)0xA05F6920)
#define HOLLY_INTERNAL_IRQ_6_MASK *((volatile uint32_t *)0xA05F6930)

#define HOLLY_INTERNAL_INTERRUPT_RENDER_FINISHED 0x00000007
#define HOLLY_INTERNAL_INTERRUPT_VBLANK_IN 0x00000008
#define HOLLY_INTERNAL_INTERRUPT_VBLANK_OUT 0x00000010
#define HOLLY_INTERNAL_INTERRUPT_HBLANK 0x00000020
#define HOLLY_INTERNAL_INTERRUPT_TRANSFER_FINISHED 0x000007C0
#define HOLLY_INTERNAL_INTERRUPT_MAPLE_DMA_FINISHED 0x00001000
#define HOLLY_INTERNAL_INTERRUPT_MAPLE_VBLANK_FINISHED 0x00002000
#define HOLLY_INTERNAL_INTERRUPT_AICA_DMA_FINISHED 0x00008000
#define HOLLY_INTERNAL_INTERRUPT_CHECK_EXTERNAL 0x40000000
#define HOLLY_INTERNAL_INTERRUPT_ERROR 0x80000000

// Caused by external sources that HOLLY manages.
#define HOLLY_EXTERNAL_IRQ_STATUS *((volatile uint32_t *)0xA05F6904)
#define HOLLY_EXTERNAL_IRQ_2_MASK *((volatile uint32_t *)0xA05F6914)
#define HOLLY_EXTERNAL_IRQ_4_MASK *((volatile uint32_t *)0xA05F6924)
#define HOLLY_EXTERNAL_IRQ_6_MASK *((volatile uint32_t *)0xA05F6934)

#define HOLLY_EXTERNAL_INTERRUPT_DIMM_COMMS 0x00000008

// Errors that have happened.
#define HOLLY_ERROR_STATUS *((volatile uint32_t *)0xA05F6908)

#endif
