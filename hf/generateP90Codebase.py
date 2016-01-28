#!/usr/bin/python
# -*- coding: UTF-8 -*-

# Copyright (C) 2014 Michel Müller, Tokyo Institute of Technology

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

#**********************************************************************#
#  Procedure        generateP90Codebase.py                             #
#  Comment          Takes one h90 file and the associated complete     #
#                   callgraph and produces a compilable F90 file       #
#  Date             2012/08/01                                         #
#  Author           Michel Müller (AOKI Laboratory)                    #
#**********************************************************************#


from xml.dom.minidom import Document
from tools.DomHelper import parseString, ImmutableDOMDocument, getClonedDocument
from optparse import OptionParser
from H90CallGraphParser import H90XMLSymbolDeclarationExtractor, H90toF90Printer, getSymbolsByName, getModuleNodesByName, getParallelRegionData, getSymbolsByRoutineNameAndSymbolName, getSymbolsByModuleNameAndSymbolName
from GeneralHelper import UsageError, openFile, getDataFromFile, setupDeferredLogging, printProgressIndicator, progressIndicatorReset
from RecursiveDirEntries import dirEntries
from H90SymbolDependencyGraphAnalyzer import SymbolDependencyAnalyzer
from io import FileIO
import os
import errno
import sys
import json
import traceback
import StringIO
import FortranImplementation
import logging

##################### MAIN ##############################
#get all program arguments
parser = OptionParser()
parser.add_option("-i", "--sourceDir", dest="sourceDir",
									help="Source directory containing all h90 files for this implementation")
parser.add_option("-o", "--outputDir", dest="outputDir",
									help="Output directory to store all the P90 files generated by this script")
parser.add_option("-c", "--callgraph", dest="callgraph",
									help="analyzed callgraph XML file to read", metavar="XML")
parser.add_option("-d", "--debug", action="store_true", dest="debug",
									help="show debug print in standard error output")
parser.add_option("-m", "--implementation", dest="implementation",
									help="specify either a FortranImplementation classname or a JSON containing classnames by template name and a 'default' entry", metavar="IMP")
parser.add_option("--optionFlags", dest="optionFlags",
									help="can be used to switch on or off the following flags (comma separated): DO_NOT_TOUCH_GPU_CACHE_SETTINGS")
(options, args) = parser.parse_args()

setupDeferredLogging('preprocessor.log', logging.DEBUG if options.debug else logging.INFO, showDeferredLogging=not options.debug)

optionFlags = [flag for flag in options.optionFlags.split(',') if flag not in ['', None]] if options.optionFlags != None else []
logging.debug('Option Flags: %s' %(optionFlags))
if options.debug and 'DEBUG_PRINT' not in optionFlags:
	optionFlags.append('DEBUG_PRINT')

if (not options.sourceDir):
		logging.error("sourceDir option is mandatory. Use '--help' for informations on how to use this module")
		sys.exit(1)

if (not options.outputDir):
		logging.error("outputDir option is mandatory. Use '--help' for informations on how to use this module")
		sys.exit(1)

if (not options.callgraph):
		logging.error("callgraph option is mandatory. Use '--help' for informations on how to use this module")
		sys.exit(1)

if (not options.implementation):
	logging.error("implementation option is mandatory. Use '--help' for informations on how to use this module")
	sys.exit(1)

filesInDir = dirEntries(str(options.sourceDir), True, 'h90')

try:
	os.mkdir(options.outputDir)
except OSError as e:
	#we want to handle if a directory exists. every other exception at this point is thrown again.
	if e.errno != errno.EEXIST:
		raise e
	pass

#   get the callgraph information
cgDoc = parseString(getDataFromFile(options.callgraph), immutable=False)

#   build up implementationNamesByTemplateName
implementationNamesByTemplateName = None
try:
	implementationNamesByTemplateName = json.loads(getDataFromFile(options.implementation))
except ValueError as e:
	logging.critical('Error decoding implementation json (%s): %s' \
		%(str(options.implementation), str(e))
	)
	sys.exit(1)
except Exception as e:
	logging.critical('Could not interpret implementation parameter as json file to read. Trying to use it as an implementation name directly')
	implementationNamesByTemplateName = {'default':options.implementation}
logging.debug('Initializing H90toF90Printer with the following implementations: %s' %(json.dumps(implementationNamesByTemplateName)))
implementationsByTemplateName = {
	templateName:getattr(FortranImplementation, implementationNamesByTemplateName[templateName])(optionFlags)
	for templateName in implementationNamesByTemplateName.keys()
}

#   parse the @domainDependant symbol declarations flags in all h90 files
#   -> update the callgraph document with this information.
#   note: We do this, since for simplicity reasons, the declaration parser relies on the symbol names that
#   have been declared in @domainDependant directives. Since these directives come *after* the declaration,
#   we need this pass
# cgDoc = getClonedDocument(cgDoc)
for fileNum, fileInDir in enumerate(filesInDir):
	parser = H90XMLSymbolDeclarationExtractor(cgDoc, implementationsByTemplateName=implementationsByTemplateName)
	parser.processFile(fileInDir)
	logging.debug("Symbol declarations extracted for " + fileInDir + "")
	printProgressIndicator(sys.stderr, fileInDir, fileNum + 1, len(filesInDir), "Symbol parsing, excluding imports")
progressIndicatorReset(sys.stderr)

#   build up symbol table indexed by module name
moduleNodesByNameWithoutImplicitImports = getModuleNodesByName(cgDoc)
symbolAnalyzer = SymbolDependencyAnalyzer(cgDoc)
symbolAnalysisByRoutineNameAndSymbolNameWithoutImplicitImports = symbolAnalyzer.getSymbolAnalysisByRoutine()
symbolsByModuleNameAndSymbolNameWithoutImplicitImports = getSymbolsByModuleNameAndSymbolName(
	ImmutableDOMDocument(cgDoc),
	moduleNodesByNameWithoutImplicitImports,
	symbolAnalysisByRoutineNameAndSymbolName=symbolAnalysisByRoutineNameAndSymbolNameWithoutImplicitImports
)

#   parse the symbols again, this time know about all informations in the sourced modules in import
#   -> update the callgraph document with this information.
for fileNum, fileInDir in enumerate(filesInDir):
	parser = H90XMLSymbolDeclarationExtractor(
		cgDoc,
		symbolsByModuleNameAndSymbolNameWithoutImplicitImports,
		implementationsByTemplateName=implementationsByTemplateName
	)
	parser.processFile(fileInDir)
	logging.debug("Symbol imports and declarations extracted for " + fileInDir + "")
	printProgressIndicator(sys.stderr, fileInDir, fileNum + 1, len(filesInDir), "Symbol parsing, including imports")
progressIndicatorReset(sys.stderr)

#   build up meta informations about the whole codebase
try:
	sys.stderr.write('Processing informations about the whole codebase\n')
	moduleNodesByName = getModuleNodesByName(cgDoc)
	parallelRegionData = getParallelRegionData(cgDoc)
	symbolAnalyzer = SymbolDependencyAnalyzer(cgDoc)
	#next line writes some information to cgDoc as a sideeffect. $$$ clean this up, ideally make cgDoc immutable everywhere for better performance
	symbolAnalysisByRoutineNameAndSymbolName = symbolAnalyzer.getSymbolAnalysisByRoutine()
	symbolsByModuleNameAndSymbolName = getSymbolsByModuleNameAndSymbolName(
		ImmutableDOMDocument(cgDoc),
		moduleNodesByName,
		symbolAnalysisByRoutineNameAndSymbolName=symbolAnalysisByRoutineNameAndSymbolName
	)
	symbolsByRoutineNameAndSymbolName = getSymbolsByRoutineNameAndSymbolName(
		ImmutableDOMDocument(cgDoc),
		parallelRegionData[2],
		parallelRegionData[1],
		symbolAnalysisByRoutineNameAndSymbolName=symbolAnalysisByRoutineNameAndSymbolName
	)
except UsageError as e:
	logging.error('Error: %s' %(str(e)))
	sys.exit(1)
except Exception as e:
	logging.critical('Error when processing meta information about the codebase: %s' %(str(e)))
	logging.info(traceback.format_exc())
	sys.exit(1)



#   Finally, do the conversion based on all the information above.
for fileNum, fileInDir in enumerate(filesInDir):
	outputPath = os.path.join(os.path.normpath(options.outputDir), os.path.splitext(os.path.basename(fileInDir))[0] + ".P90.temp")
	printProgressIndicator(sys.stderr, os.path.basename(fileInDir), fileNum + 1, len(filesInDir), "Converting to Standard Fortran")
	outputStream = FileIO(outputPath, mode="wb")
	try:
		f90printer = H90toF90Printer(
			ImmutableDOMDocument(cgDoc), #using our immutable version we can speed up ALL THE THINGS through caching
			implementationsByTemplateName,
			outputStream,
			moduleNodesByName,
			parallelRegionData,
			symbolAnalysisByRoutineNameAndSymbolName,
			symbolsByModuleNameAndSymbolName,
			symbolsByRoutineNameAndSymbolName,
		)
		f90printer.processFile(fileInDir)
	except UsageError as e:
		logging.error('Error: %s' %(str(e)))
		sys.exit(1)
	except Exception as e:
		logging.critical('Error when generating P90.temp from h90 file %s: %s%s\n' \
			%(str(fileInDir), str(e), traceback.format_exc())
		)
		logging.info(traceback.format_exc())
		os.unlink(outputPath)
		sys.exit(1)
	finally:
		outputStream.close()
progressIndicatorReset(sys.stderr)