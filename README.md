# Naomi Toolchain & Libraries

A minimal Naomi homebrew environment, very loosely based off of KallistiOS toolchain work but bare metal and implemented from the ground up on the Naomi. This assumes that you have a Linux computer with standard prerequisites for compiling gcc/newlib/binutils already installed as well as a working Python 3.6+ installation available. The Naomi system library is minimal, but includes support for many POSIX features such as filesystems and basic pthreads. Support for all major built-in hardware is included, including JVS, EEPROM reading/writing, PowerVR 2D and 3D operations, built-in matrix and vector operations, reading and writing from the DIMM cartridge and communication with an external host through the net dimm. Additionally, a 3rdparty repository has been setup and a few ports are available. Both the system libraries and the 3rdparty repo will continue to get fleshed out.

## Getting Started

To get started, create a directory named `/opt/toolchains/naomi` and copy the contents of the `setup/` directory to it. This directory and the copied contents should be user-owned and user-writeable. Then, cd to `/opt/toolchains/naomi` and in order run `./download.sh` (downloads toolchain sources), `./unpack.sh` (unpacks the toolchain to be built), `make` (builds the toolchain and installs it in the correct directories), `make gdb` (builds gdb for SH-4 only) and finally `./cleanup.sh`. If everything is successful, you should have a working compiler and C standard library as well as debugging tools. Now, every time you wish to use the toolchain, you should run `source /opt/toolchains/naomi/env.sh` to set up your local environment to use the tools you just build.

Next, you will need to set up the python virtualenv and compile the system libraries. For convenience the python virtualenv, libnaomi, libnaomimessage, libnaomisprite and the examples will all be built if you run `make` in the `homebrew/` directory. Assuming your toolchain from the previous paragraph is working, all you need to do is run `make` inside the root directory of this repository. If you receive error messages about "Command not found", you have not activated your Naomi enviornment by running `source /opt/toolchains/naomi/env.sh`. Note that by default there are no 3rd party libraries installed and thus libnaomi support for things like font rendering and compressed messages is disabled. To enable 3rd party libraries, first run the above `make` to ensure that the base libraries are compiled properly and then run `make -C 3rdparty install` in the `homebrew/` directory which will fetch, configure, make and install all of the 3rd party libraries. Then, back in the `homebrew/` directory run `make clean` and then re-run `make` to rebuild libnaomi and the examples with 3rd party support. The resulting binary files in the various example directory can be loaded in Demul or net booted to a Naomi to execute them.

Finally, once you are happy with everything, run `make install` from the root of the repository which will install libnaomi into the toolchain directory from the first paragraph. After doing this, you can create a project by basing off of the `minimal/` example which will compile to the Naomi platform. Remember, if you get "Command not found" errors when trying to build your project, run `source /opt/toolchains/naomi/env.sh` to activate the environment.

## Updating libnaomi

When libnaomi changes, you'll most likely want to pull those changes so you can use them in your project. Once you've gotten your toolchain setup and isntalled its an easy process. First, make sure that you've activated the Naomi enviornment with `source /opt/toolchains/naomi/env.sh`. Then, at the root of the repository, run `git pull` followed by `make install`. This should fetch everything that changed and rebuild the libraries for you to use. Note that if the compiler itself changes, you should follow the entire getting started section again. However, under most circumstances (such as new features, bugfixes to libnaomi or documentation improvements) you can simply `make install` to compile and update your toolchain.

## Developing With libnaomi

It is recommended to base your project off of the the minimal hello world example in the `minimal/` directory. You are free to write your own makefiles from scratch. However, lots of features are provided for you automatically when you base off of the minimal example. These include automatic dependency tracking (for source, header and library files used in your project), available tools for converting resources to includes, tools for converting images to texture and sprite formats, tools for building a ROMFS and the crucial ROM header creation tool. It also includes proper CFLAGS and LDFLAGS which ensures that your code actually compiles and links against libnaomi to create a working binary that can execute on a Naomi. Note that anything which is done in an example's makefile can also be done in your own makefile, so be sure to look at the examples for how to do just about everything.

Homebrew is welcome to make use of additional facilities that allow for redirecting stdout/stderr to the host console for debugging. Notably, the test executable that is generated out of the `tests/` directory makes use of this to display the test results both on the Naomi and on the host's console. To intercept such messages, you can run `/opt/toolchains/naomi/tools/stdioredirect` and it will handle displaying anything that the target is sending to stdout or stderr using printf(...) or fprintf(stderr, ...) calls. Note that the homebrew program must link against libnaomimessage.a and initialize the console redirect hook for this to work properly. See the `debugprint` example for how to do this properly. If GDB debugging is too advanced for you this might be adequate for debugging your program when it is running on target.

For ease of tracking down program bugs, an exception handler is present which prints out the system registers, stack address and PC at the point of exception. For further convenience, debugging information is left in an elf file that resides in the `build/` directory of an example you might be building or of any project based off of the minimal example discussed above. To locate the offending line of code when an exception is displayed, you can run `/opt/toolchains/naomi/sh-elf/bin/sh-elf-addr2line --exe=build/naomi.elf <displayed PC address>` and the function and line of code where the exception occurred will be displayed for you.

Additionally, libnaomi has GDB remote debugging support allowing you to attach to a program running on the Naomi and step through as well as debug the program. To debug your program, first activate the GDB server by running `/opt/toolchains/naomi/tools/gdbserver` and then run GDB with `/opt/toolchains/naomi/sh-elf/bin/sh-elf-gdb build/naomi.elf`. To attach to the target once GDB is running and has read symbols from your compiled program, type `target remote :2345`. If all is successful, your program will halt and you can examine your program in real-time on the target. If you are trying to track down an intermittent problem, you can connect and then continue. If your program crashes on the Naomi and displays an invariant or exception screen, GDB will be interrupted and you can examine stack traces and the locals of all threads. You can also connect and halt the execution of the program with Ctrl+C inside the GDB console and then single-step through code while examining locals. Note that you do not noeed to compile any support for this as GDB support is built into libnaomi.

## Developing libnaomi Itself

libnaomi and the associated examples and tests are self-contained in the repo. You do not need to `make install` in order to test libnaomi inside the `tests/` directory or in any of the examples. When adding a new feature to libnaomi you should consider whether that feature is critial to the operation of the Naomi itself. If it is, then the feature should go into libnaomi directly. If it is not, then a new library should be created much like libnaomimessage and libnaomisprite in order to keep the code somewhat clean. Note that in either case it is highly recommended to either create a new example showing how to use the code or augment an existing example to include use of the code you are adding. Also, whenever possible a test should be written in the `tests/` directory to exercise the feature. These tests get run often in Demul and on a real Naomi so it is a good way to ensure that your code does not regress due to unrelated changes.

## Extent of Support

libnaomi is the system library and assocated headers which provides all of the below features. It includes all the hardware drivers as well as the POSIX compatibility layer and C runtime support functions necessary to compile modern C or C++ code for the Naomi platform. The majority of the C stdlib is provided by a combination of GCC and newlib and the POSIX compatibility layer is provided by a combination of newlib and libnaomi. The C++ stdlib is provided by GCC and is bridged to various low-level libraries under the hood.

The audio system is robust and fairly complete. The AICA driver allows for up to 62 sounds to be registered and played back at-will, and two channels are reserved for a stereo ringbuffer which is writeable from the SH-4 side. This can be used to stream audio from a library that is decoding it, or for mixing your own sounds. If you wish, you can load your own AICA binary and use that instead but if you do this then the normal audio system in libnaomi will not be available. The `audiotest` example will show you the basics for how to use the audio system.

The cart system allows for full reading and writing to/from the cart. This works in tandem with any net dimm plugged into the system, so you can write data to the cart from the net dimm and read it on the Naomi and vice versa. This is used in the GDB driver to provide reliable bulk transfer of data. A small library for reading the cart header and parsing out the program's main and test entrypoint from it is also available. The `carttest` example will show you the basics for how to use the cart system.

The DIMM communication system implements the DIMM communication protocol that is used by the net dimm and the BIOS to peek/poke memory. By default, no handler for reading/writing system memory is installed but a default one can be installed. Alternatively, your own set of read/write callbacks can be implemented which are called in interrupt context when the net dimm is used to peek or poke memory. This is used both in the GDB driver to provide external interrupts and by thet message subsystem to pass small messages between the host and Naomi. The `netdimm` example will show you the basics for how to use the DIMM communication module, and the `debugprint` example shows how to use the include libnaomimessage library which sits on top of the DIMM communication system.

The EEPROM system is robust and complete, supporting full system and game section settings, automatic recovery of partially-written EEPROMs and full compatibility with the BIOS. The `eepromtest` example shows how to read and write the full EEPROM and the `tests/test_eeprom.c` test file shows how to use the high-level EEPROM library.

The GDB system is robust and fairly complete. It allows breakpoints to be set, single-stepping of code as well as memory and register reading and modification. It is fully integrated with the libnaomi thread system (and consequently pthreads) which allows you to inspect the stack, locals and running state of all active threads in realtime. This can be used in conjunction with the leftover `naomi.elf` file in the `build/` directory of any example or any homebrew based off of the `minimal` makefile example to achieve source-level on-target debugging. It does not support memory watchpoints or some esoteric GDB features. There is no example for this as GDB is built into all examples.

The interrupt system is robust and fairly complete, supporting most critical HOLLY and system interrupts. This is mostly used by the microkernel to provide support for other systems such as the video, TA, GDB and thread systems. You will usually not interact directly with this system outside of the `ATOMIC` macros and then `irq_disable()` and `irq_restore()` in order to gain temporary exclusive access to the SH-4. There is no example for this as the microkernel is used by all examples.

The maple system is fairly complete but relies on the BIOS to initialize both the maple chip as well as the JVS interface. Because the BIOS (and commercial games) load their own code stub to the maple chip after a reset, libnaomi relies on the BIOS so as not to include a copyrighted binary blob in its distribution. In practice, this does not matter much since only the H BIOS allows for net booting and this is the only current method of achieving code execution on the system. Support is provided through the EEPROM system for accessing the maple-attached EEPROM, and a library is provided for polling for JVS controls. Only one player and two player setups have been tested with this approach and there are some reports of partial failure with some JVS devices, namely OpenJVS. The `inputtest` example will show you the basics for how to use the maple system.

Drivers for the built-in SH-4 matrix and vector instructions are provided in the matrix and vector subsystem. These together provide a set of libraries for manipulating the system matrix to perform affine and perspective transformations of sets of coordinates as well as calculating normals. While this system is complete, it is fairly barebones and quite low level. There is no higher-level 3D library available. The `pvrtest` example shows using these libraries for 3D and the `tests/test_matrix.c` and `tests/test_vector.c` test files show a variety of basic uses.

The POSIX system is fairly robust and includes a ROMFS as well as full filesystem and directory support. It also includes a partial pthreads implementation which is fully integrated with the thread system. Expect that if a POSIX function is defined it conforms to the POSIX spec. Several 3rdparty libraries have been ported successfully to the Naomi using this POSIX compatibility system. Note that the microkernel is much simpler than the Linux kernel and only supports system-level threads. As such, there is no support for the MMU and you should not expect more complex or esoteric features of pthreads to work. The `carttest` example shows how to initialize and use the ROMFS through standard file operations and the `debugprint` example shows how to use the stdio system from a host.

The RTC system is robust and complete and supports both reading and writing the system clock. This is also integrated into the POSIX system. Assuming you have your time set correctly in the BIOS, you should be able to read it from code using the RTC or the POSIX modules. The `rtctest` example will show you the basics for how to use the RTC system and the `tests/test_rtc.c` test shows how to use the low-level functions.

The video system is robust and fairly well-featured but quite low level. There is full support for software framebuffers including several helpful functions. There is also support for the TA/PowerVR system including several functions for setting up and managing displaylists as well as helper functions for rendering quads and triangle strips. In conjunction with the matrix and vector drivers this can be used to implement a full 3D game with textures and dynamic lighting. There is also helper code tied into the optionally-compiled freetype 3rdparty library which allows for both software and hardware-accelerated rendering of truetype fonts. Note that the PowerVR is very particular in how it wishes to receive displaylists so not all orders of operation between the framebuffer and PowerVR are possible. In general, it is recommended to draw your scene using the TA and then augment with any debugging console after the fact. The `hellonaomi` example shows off various software framebuffer functions, the `pvrtest` example shows off basic 3D support and the `spritetest` example shows off basic 2D support using the include libnaomisprite library which sits on top of the video system. The `advancedpvrtest` example shows off mixing multiple texture types as well as mixing hardware and software rendering for the same frame.

The thread system is robust and provides support for threading, mutexes, semaphores and global counters. It also supports high-priority RTOS-like waiting for things such as vblank, TA displaylist fill and rendering complete triggers. The basic threading support is also integrated with pthreads. Basic support for things like priority bands, recursive mutexes and priority bumping for critical events is included. The thread system is also integrated with GDB so you can look at the state of each thread when debugging or single-stepping. The included pthreads wrapper includes support for thread creation/updating/cancellation/destruction, mutexes, spinlocks, one-time init and thread-local storage. The `threadtest` example shows off the various features of the threading system and the `pvrtest` shows how to wait for PowerVR and vblank events to successfully render without screen tearing.

The timer system is robust and complete, supporting the three hardware timers that the SH-4 provides. This is mostly used by the microkernel to provide profiling and task preemption. You will generally not interact directly with this system outside of the `profile_start()` and `profile_end()` functions and the `timer_wait()` spinloop function. Because the SH-4 is so limited in hardware timers, they are multiplexed in software so that you can start many more of them for things such as key repeats or waiting for particular durations before updating animations. There is no example for the timer system but various examples such as `hellonaomi` use the timer system to calculate framerate and draw time per-frame.

## Additional Docs

If you are looking for a great resource for programming, the first thing I would recommend is https://github.com/Kochise/dreamcast-docs which is mostly relevant to the Naomi. For memory maps and general low-level stuff, Mame's https://github.com/mamedev/mame/blob/master/src/mame/drivers/naomi.cpp is extremely valuable. Also the headers for various libnaomi modules contain descriptions for how to use the functions found within. And of course, you can look at the source code to the various examples to see some actual code.
