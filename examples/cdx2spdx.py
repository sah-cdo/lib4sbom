# Copyright (C) 2024 Anthony Harrison
# SPDX-License-Identifier: Apache-2.0

import sys
from lib4sbom.parser import SBOMParser
from lib4sbom.generator import SBOMGenerator

# Simple CycloneDX to SPDX SBOM converter

# Set up SBOM parser
test_parser = SBOMParser()
# Load SBOM - will autodetect SBOM type
test_parser.parse_file(sys.argv[1])

# Set up SPDX-JSON generator
test_generator = SBOMGenerator(False, sbom_type="spdx", format="json")
# Generate sbom in JSON format to console (default)
test_generator.generate("ACMEApp", test_parser.get_sbom())

