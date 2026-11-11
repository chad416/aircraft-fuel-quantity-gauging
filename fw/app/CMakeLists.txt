# SPDX-License-Identifier: MIT
cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(fq_fw C)

set(FQ_LIB ${CMAKE_CURRENT_SOURCE_DIR}/../lib/fq)
file(GLOB FQ_SRC ${FQ_LIB}/src/*.c)

target_sources(app PRIVATE src/main.c ${FQ_SRC})
target_include_directories(app PRIVATE ${FQ_LIB}/include)
target_compile_options(app PRIVATE -Wall -Wextra -Werror)
