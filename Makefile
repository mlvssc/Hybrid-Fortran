# Copyright (C) 2016 Michel Müller, Tokyo Institute of Technology

# This file is part of Hybrid Fortran.

# Hybrid Fortran is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Hybrid Fortran is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with Hybrid Fortran. If not, see <http://www.gnu.org/licenses/>.

#***************************************************************************#
#  Makefile to create an example project and run tests.                     #
#                                                                           #
#  Date             2014/07/11                                              #
#  Author           Michel Müller (Titech)                                  #
#                                                                           #
#***************************************************************************#
SHELL=/bin/bash
TEMPLATEDIR=${HF_DIR}/hf_template/
EXAMPLEDIR=${HF_DIR}/example/
EXAMPLEDIR_SOURCE=${EXAMPLEDIR}source/

TEST_PROJECTS=examples/demo examples/5D_parallel_vector examples/simple_stencil examples/stencil_with_local_array examples/stencil_with_passed_in_scalar_from_array examples/hybrid_device_and_host_routines examples/module_data examples/multi_kernel_routines examples/branches_around_parallel_regions examples/array_accessor_functions examples/early_returns examples/mixed_implementations examples/strides examples/poisson2d_fem_iterative examples/diffusion3d examples/particle examples/midaco_solver
ADDITIONAL_TEST_PROJECTS=pp examples/mpi_multi_gpu_scatter examples/tracing examples/simple_weather

TEST_TARGETS=$(addprefix test_,$(TEST_PROJECTS))
CLEAN_TARGETS=$(addprefix clean_,$(TEST_PROJECTS))
ADDITIONAL_TEST_TARGETS=$(addprefix test_,$(ADDITIONAL_TEST_PROJECTS))
ALL_TEST_PROJECTS=${TEST_PROJECTS} ${ADDITIONAL_TEST_PROJECTS}

.PHONY: all example tests ${TEST_TARGETS} ${ADDITIONAL_TEST_TARGETS}

all: example

tests: unit test_example ${TEST_TARGETS}

clean: clean_example ${CLEAN_TARGETS}

unit:
	@echo "###########################################################################################"
	@echo "########################## unit tests #####################################################"
	@echo "###########################################################################################"
	@python ${HF_DIR}/hf/unit.py

#note: cp -n does not exist in older GNU utils, so we emulate it here for compatibility
example:
	@mkdir -p ${EXAMPLEDIR}
	@mkdir -p ${EXAMPLEDIR_SOURCE}
	@if [ ! -e ${EXAMPLEDIR_SOURCE}example.h90 ]; then \
	    cp -f ${TEMPLATEDIR}example_example.h90 ${EXAMPLEDIR_SOURCE}example.h90; \
	fi; \
	if [ ! -e ${EXAMPLEDIR_SOURCE}storage_order.F90 ]; then \
	    cp -f ${TEMPLATEDIR}example_storage_order.F90 ${EXAMPLEDIR_SOURCE}storage_order.F90; \
	fi; \
	if [ ! -e ${EXAMPLEDIR}configure ]; then \
	    cp -f ${TEMPLATEDIR}configureForProject.sh ${EXAMPLEDIR}configure; \
	fi

test_example: example
	@echo "###########################################################################################"
	@echo "########################## attempting to test example #####################################"
	@echo "###########################################################################################"
	@rm -r example
	@make example
	@cd example && ./configure
	@echo "----- debug target ------"
	@cd example && make clean && make tests DEBUG=1
	@echo "----- default target ------"
	@cd example && make clean && make tests

define test_rules
  test_$(1):
	@echo "###########################################################################################"
	@echo "########################## attempting to test $(1) ###############################"
	@echo "###########################################################################################"
	@cd $(1) && ./configure
	@echo "----- debug target ------"
	@cd $(1) && make clean && make tests DEBUG=1
	@echo "----- default target ------"
	@cd $(1) && make clean && make tests
endef

clean_example:
	@cd example && make clean

define clean_rules
  clean_$(1):
	@cd $(1) && make clean
endef

$(foreach project,$(ALL_TEST_PROJECTS),$(eval $(call test_rules,$(project))))
$(foreach project,$(ALL_TEST_PROJECTS),$(eval $(call clean_rules,$(project))))
