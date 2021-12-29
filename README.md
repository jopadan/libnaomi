# Naomi Toolchain & Libraries

A minimal Naomi homebrew environment, very loosely based off of KallistiOS toolchain work but bare metal and implemented from the ground up on the Naomi. This assumes that you have a Linux computer with standard prerequisites for compiling gcc/newlib/binutils already installed. The Naomi system library is minimal, but includes support for many POSIX features such as filesystems and pthreads. Support for all major built-in hardware is included, including JVS, EEPROM reading/writing, PowerVR 2D and 3D operations, built-in matrix and vector operations, reading and writing from the DIMM cartridge and communication with an external host through the net dimm. Additionally, a 3rdparty repository has been setup and a few ports are available. Both the system libraries and the 3rdparty repo will continue to get fleshed out.

To get started, create a directory named "/opt/toolchains/naomi" and copy the contents of the `setup/` directory to it. This directory and the copied contents should be user-owned and user-writeable. Then, cd to "/opt/toolchains/naomi" and in order run `./download.sh` (downloads toolchain sources), `./unpack.sh` (unpacks the toolchain to be built), `make` (builds the toolchain and installs it in the correct directories), `make gdb` (builds gdb for SH-4 only) and finally `./cleanup.sh`. If everything is successful, you should have a working compiler and C standard library.

After this, you will need to set up a python virtualenv for the various build utility dependencies. To do that, run `make pyenv` from the `homebrew/` directory. This should create a virtualenv in a place where the various tools can find it and install the correct dependencies so that everything will work. Note that this does assume you have a working python3 3.6+ installation with pip and venv packages available. Once this is done, you are ready to start compiling libnaomi as well as the tests and examples!

The next thing you will need to do is build libnaomi, the system support library that includes the C/C++ runtime setup, newlib system hooks and various low-level drivers. To do that, run `make` from inside the `libnaomi/` directory. If a `libnaomi.a` file is created this means that the toolchain is set up properly and the system library was successfully built! If you receive error messages about "Command not found", you have not activated your Naomi enviornment by running `source /opt/toolchains/naomi/env.sh`. Then, you will want to run `make` from inside the `libnaomi/message/` directory to build the message library which is required for one of the examples to build. Similarly, if a `libnaomimessage.a` file is created that means you built it successfully! Finally, to build any examples that are included, first activate the Naomi enviornment by running `source /opt/toolchains/naomi/env.sh`, and then run `make` in the directory of the example you want to run. The resulting binary file can be loaded in Demul or netbooted to a Naomi with a netdimm.

For convenience the python virtualenv, libnaomi and the examples will all be built if you run `make` in the `homebrew/` directory. That means that you can skip all of the steps in the above two paragraphs assuming that your toolchain setup is working. Note that by default there are no 3rd party libraries installed and thus libnaomi support for things like font rendering is disabled. To enable 3rd party libraries, first run `make -C 3rdparty install` in the `homebrew/` directory which will fetch, configure, make and install all of the 3rd party libraries. Then, back in the `homebrew/` directory run `make clean` and then re-run `make` to rebuild libnaomi with 3rd party support.

Once you are satisfied that the toolchain is working and all of the examples are building, you can install libnaomi into the toolchain path so that you can reference it from your own compiled code. To do that, run `make install` in the `homebrew/` directory. This will blow away and remake the python virtualenv for you and install all the proper dependencies needed, copy the libraries and header files, copy the ldscripts and build utilities such as makerom, and finally copy a `Makefile.base` that you can source to get rid of a lot of the boilerplate of makefiles. If all goes well then you should be able to cd into the `homebrew/minimal/` directory and run `make` there. You should base your own build setup off of the makefile found in this directory. Remember to source `/opt/toolchains/naomi/env.sh` before building so that your makefile can find `Makefile.base` and everything else that comes along with it.

For ease of tracking down program bugs, an exception handler is present which prints out the system registers, stack address and PC at the point of exception. For further convenience, debugging information is left in an elf file that resides in the build/ directory of an example you might be building. To locate the offending line of code when an exception is displayed, you can run `/opt/toolchains/naomi/sh-elf/bin/sh-elf-addr2line --exe=build/naomi.elf <displayed PC address>` and the function and line of code where the exception occurred will be displayed for you. Additionally, there is GDB remote debugging support allowing you to attach to a program running on the Naomi and step through as well as debug the program. To debug your program, first activate the GDB server by running `/opt/toolchains/naomi/tools/gdbserver` and then run GDB with `/opt/toolchains/naomi/sh-elf/bin/sh-elf-gdb build/naomi.elf`. To attach to the target once GDB is running and has read symbols from your compiled program, type `target remote :2345`. If all is successful, your program will halt and you can examine your program in real-time on the target.

Homebrew is also welcome to make use of additional facilities that allow for redirecting stdout/stderr to the host console for debugging. Notably, the test executable that is generated out of the `tests/` directory will do this. To intercept such messages, you can run `/opt/toolchains/naomi/tools/stdioredirect` and it will handle displaying anything that the target is sending to stdout or stderr using printf(...) or fprintf(stderr, ...) calls. Note that the homebrew program must link against libnaomimessage.a and initialize the console redirect hook for this to work properly. If GDB debugging is too advanced for you this might be adequate for debugging your program when it is running on target.

For the minimal hello world example which can be compiled from its own repository outside of this one, see the `minimal/` directory. It contains a makefile that works with this toolchain if properly installed (using `make install` at the root) and sourced (running `source /opt/toolchains/naomi/env.sh`) in the shell you are compiling in. The included c file is extremely minimal and only illustrates the most basic text output. However, you can use this as the baseline for any new project you are starting by copying the files to a new directory and changing things as needed.

## Extent of Support

The audio system is robust and fairly complete. The AICA driver allows for up to 62 sounds to be registered and played back at-will, and two channels are reserved for a stereo ringbuffer which is writeable from the SH-4 side. This can be used to stream audio from a library that is decoding it, or for mixing your own sounds. If you wish, you can load your own AICA binary and use that instead but if you do this then the normal audio system in libnaomi will not be available.

The cart system allows for full reading and writing to/from the cart. This works in tandem with any net dimm plugged into the system, so you can write data to the cart from the net dimm and read it on the Naomi and vice versa. This is used in the GDB driver to provide reliable bulk transfer of data. A small library for reading the cart header and parsing out the program's main and test entrypoint from it is also available.

The DIMM communication system implements the DIMM communication protocol that is used by the net dimm and the BIOS to peek/poke memory. By default, no handler for reading/writing system memory is installed but a default one can be installed. Alternatively, your own set of read/write callbacks can be implemented which are called in interrupt context when the net dimm is used to peek or poke memory. This is used both in the GDB driver to provide external interrupts and by thet message subsystem to pass small messages between the host and Naomi.

The EEPROM system is robust and complete, supporting full system and game section settings, automatic recovery of partially-written EEPROMs and full compatibility with the BIOS.

The GDB system is robust and fairly complete. It allows breakpoints to be set, single-stepping of code as well as memory and register reading and modification. It is fully integrated with the libnaomi thread system (and consequently pthreads) which allows you to inspect the stack, locals and running state of all active threads in realtime. This can be used in conjunction with the leftover `naomi.elf` file in the `build/` directory of any example or any homebrew based off of the `minimal` makefile example to achieve source-level on-target debugging. It does not support memory watchpoints or some esoteric GDB features.

The interrupt system is robust and fairly complete, supporting most critical HOLLY and system interrupts. This is mostly used by the microkernel to provide support for other systems such as the video, TA, GDB and thread systems. You will usually not interact directly with this system outside of the `ATOMIC` macros and then `irq_disable()` and `irq_restore()` in order to gain temporary exclusive access to the SH-4.

The maple system is fairly complete but relies on the BIOS to initialize both the maple chip as well as the JVS interface. Because the BIOS (and commercial games) load their own code stub to the maple chip after a reset, libnaomi relies on the BIOS so as not to include a copyrighted binary blob in its distribution. In practice, this does not matter much since only the H BIOS allows for net booting and this is the only current method of achieving code execution on the system. Support is provided through the EEPROM system for accessing the maple-attached EEPROM, and a library is provided for polling for JVS controls. Only one player and two player setups have been tested with this approach and there are some reports of partial failure with some JVS devices, namely OpenJVS.

Drivers for the built-in SH-4 matrix and vector instructions are provided in the matrix and vector subsystem. These together provide a set of libraries for manipulating the system matrix to perform affine and perspective transformations of sets of coordinates as well as calculating normals. While this system is complete, it is fairly barebones and quite low level. There is no higher-level 3D library available.

The POSIX system is fairly robust and includes a ROMFS as well as full filesystem and directory support. It also includes a partial pthreads implementation which is fully integrated with the thread system. Expect that if a POSIX function is defined it conforms to the POSIX spec. Several 3rdparty libraries have been ported successfully to the Naomi using this POSIX compatibility system. Note that the microkernel is much simpler than the Linux kernel and only supports system-level threads. As such, there is no support for the MMU and you should not expect more complex or esoteric features of pthreads to work.

The RTC system is robust and complete and supports both reading and writing the system clock. This is also integrated into the POSIX system. Assuming you have your time set correctly in the BIOS, you should be able to read it from code using the RTC or the POSIX modules.

The video system is robust and fairly well-featured but quite low level. There is full support for software framebuffers including several helpful functions. There is also support for the TA/PowerVR system including several functions for setting up and managing displaylists as well as helper functions for rendering quads and triangle strips. In conjunction with the matrix and vector drivers this can be used to implement a full 3D game with textures and dynamic lighting. There is also helper code tied into the optionally-compiled freetype 3rdparty library which allows for both software and hardware-accelerated rendering of truetype fonts. Note that the PowerVR is very particular in how it wishes to receive displaylists so not all orders of operation between the framebuffer and PowerVR are possible. In general, it is recommended to draw your scene using the TA and then augment with any debugging console after the fact.

The timer system is robust and complete, supporting the three hardware timers that the SH-4 provides. This is mostly used by the microkernel to provide profiling and task preemption. You will generally not interact directly with this system outside of the `profile_start()` and `profile_end()` functions and the `timer_wait()` spinloop function. Because the SH-4 is so limited in hardware timers, they are multiplexed in software so that you can start many more of them for things such as key repeats or waiting for particular durations before updating animations.

## Additional Docs

If you are looking for a great resource for programming, the first thing I would recommend is https://github.com/Kochise/dreamcast-docs which is mostly relevant to the Naomi. For memory maps and general low-level stuff, Mame's https://github.com/mamedev/mame/blob/master/src/mame/drivers/naomi.cpp is extremely valuable. Also the headers for various libnaomi modules contain descriptions for how to use the functions found within. And of course, you can look at the source code to the various examples to see some actual code.
