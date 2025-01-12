# Copyright (C) 2023 Anthony Harrison
# SPDX-License-Identifier: Apache-2.0

import json
import os

import defusedxml.ElementTree as ET

from lib4sbom.data.document import SBOMDocument
from lib4sbom.data.modelcard import ModelDataset, ModelGraphicset, SBOMModelCard
from lib4sbom.data.package import SBOMPackage
from lib4sbom.data.relationship import SBOMRelationship
from lib4sbom.data.vulnerability import Vulnerability


class CycloneDXParser:
    def __init__(self):
        self.debug = os.getenv("LIB4SBOM_DEBUG") is not None
        self.cyclonedx_package = SBOMPackage()
        self.packages = {}
        self.id = {}
        self.component_id = 0
        self.model_card = SBOMModelCard()

    def parse(self, sbom_file):
        """parses CycloneDX BOM file extracting package name, version and license"""
        if sbom_file.endswith((".bom.json", ".cdx.json", ".json")):
            return self.parse_cyclonedx_json(sbom_file)
        elif sbom_file.endswith((".bom.xml", ".cdx.xml", ".xml")):
            return self.parse_cyclonedx_xml(sbom_file)
        else:
            return {}, {}, {}, [], []

    def _governance_element(self, element):
        elements = []
        for item in element:
            entry = {}
            if "organization" in item:
                if "name" in item["organization"]:
                    entry["organization"] = item["organization"]["name"]
            if "contact" in item:
                if "email" in item["contact"]:
                    entry["contact"] = item["contact"]["email"]
            if len(entry) > 0:
                elements.append(entry)
        return elements

    def _cyclonedx_mlmodel(self, d):
        # Machine learning model data
        self.model_card.initialise()
        if "bom-ref" in d["modelCard"]:
            self.model_card.set_id(d["modelCard"]["bom-ref"])
        if "modelParameters" in d["modelCard"]:
            if "approach" in d["modelCard"]["modelParameters"]:
                self.model_card.set_model_type(
                    d["modelCard"]["modelParameters"]["approach"]["type"]
                )
            if "task" in d["modelCard"]["modelParameters"]:
                self.model_card.set_task(d["modelCard"]["modelParameters"]["task"])
            if "architectureFamily" in d["modelCard"]["modelParameters"]:
                self.model_card.set_architecture(
                    d["modelCard"]["modelParameters"]["architectureFamily"]
                )
            if "modelArchitecture" in d["modelCard"]["modelParameters"]:
                self.model_card.set_model(
                    d["modelCard"]["modelParameters"]["modelArchitecture"]
                )
            if "datasets" in d["modelCard"]["modelParameters"]:
                for dataset in d["modelCard"]["modelParameters"]["datasets"]:
                    dataset_info = ModelDataset()
                    dataset_info.set_dataset_type(dataset["type"])
                    dataset_info.set_name(dataset["name"])
                    dataset_info.set_id(dataset.get("bom-ref"))
                    # Contents
                    if "contents" in dataset:
                        if "attachment" in dataset["contents"]:
                            dataset_info.set_contents(
                                dataset["contents"]["attachment"]["content"]
                            )
                        if "url" in dataset["contents"]:
                            dataset_info.set_contents(url=dataset["contents"]["url"])
                        if "properties" in dataset["contents"]:
                            for property in dataset["contents"]["properties"]:
                                dataset_info.set_conent_property(
                                    property["name"], property["value"]
                                )
                    dataset_info.set_classification(dataset["classification"])
                    if "sensitiveData" in dataset:
                        dataset_info.set_sensitive_data(dataset["sensitiveData"])
                    # Graphics
                    if "graphics" in dataset:
                        graphicset = ModelGraphicset()
                        graphicset.set_description(dataset["graphics"]["description"])
                        for graphic in dataset["graphics"]["collection"]:
                            image = graphic["image"]
                            graphicset.add_image(
                                graphic.get("name"), image.get("content")
                            )
                        dataset_info.set_graphics(graphicset.get_graphicset())
                    if "description" in dataset:
                        dataset_info.set_description(dataset["description"])
                    # Governance
                    if "governance" in dataset:
                        if "custodians" in dataset["governance"]:
                            for entry in self._governance_element(
                                dataset["governance"]["custodians"]
                            ):
                                dataset_info.set_governance(custodian=entry)
                        if "stewards" in dataset["governance"]:
                            for entry in self._governance_element(
                                dataset["governance"]["stewards"]
                            ):
                                dataset_info.set_governance(steward=entry)
                        if "owners" in dataset["governance"]:
                            for entry in self._governance_element(
                                dataset["governance"]["owners"]
                            ):
                                dataset_info.set_governance(owner=entry)
                    self.model_card.set_dataset(dataset_info.get_dataset())
            if "inputs" in d["modelCard"]["modelParameters"]:
                for inputs in d["modelCard"]["modelParameters"]["inputs"]:
                    self.model_card.set_inputs(inputs["format"])
            if "outputs" in d["modelCard"]["modelParameters"]:
                for outputs in d["modelCard"]["modelParameters"]["outputs"]:
                    self.model_card.set_outputs(outputs["format"])
        if "quantitativeAnalysis" in d["modelCard"]:
            if "performanceMetrics" in d["modelCard"]["quantitativeAnalysis"]:
                for metric in d["modelCard"]["quantitativeAnalysis"][
                    "performanceMetrics"
                ]:
                    lowerbound = upperbound = None
                    if "confidenceInterval" in metric:
                        interval = metric["confidenceInterval"]
                        lowerbound = interval.get("lowerBound")
                        upperbound = interval.get("upperBound")
                    self.model_card.set_performance(
                        metric.get("type"),
                        metric.get("value"),
                        metric.get("slice"),
                        lowerbound,
                        upperbound,
                    )
            if "graphics" in d["modelCard"]["quantitativeAnalysis"]:
                graphicset = ModelGraphicset()
                graphicset.set_description(
                    d["modelCard"]["quantitativeAnalysis"]["graphics"]["description"]
                )
                for graphic in d["modelCard"]["quantitativeAnalysis"]["graphics"][
                    "collection"
                ]:
                    image = graphic["image"]
                    graphicset.add_image(graphic.get("name"), image.get("content"))
                self.model_card.set_graphics(graphicset.get_graphicset())
        if "considerations" in d["modelCard"]:
            if "users" in d["modelCard"]["considerations"]:
                for user in d["modelCard"]["considerations"]["users"]:
                    self.model_card.set_user(user)
            if "useCases" in d["modelCard"]["considerations"]:
                for usecase in d["modelCard"]["considerations"]["useCases"]:
                    self.model_card.set_usecase(usecase)
            if "technicalLimitations" in d["modelCard"]["considerations"]:
                for limitation in d["modelCard"]["considerations"][
                    "technicalLimitations"
                ]:
                    self.model_card.set_limitation(limitation)
            if "performanceTradeoffs" in d["modelCard"]["considerations"]:
                for tradeoff in d["modelCard"]["considerations"][
                    "performanceTradeoffs"
                ]:
                    self.model_card.set_tradeoff(tradeoff)
            if "ethicalConsiderations" in d["modelCard"]["considerations"]:
                for consideration in d["modelCard"]["considerations"][
                    "ethicalConsiderations"
                ]:
                    self.model_card.set_ethicalrisk(
                        consideration.get("name"),
                        consideration.get("mitigationStrategy"),
                    )
            if "fairnessAssessments" in d["modelCard"]["considerations"]:
                for assessment in d["modelCard"]["considerations"][
                    "fairnessAssessments"
                ]:
                    self.model_card.set_fairness(
                        assessment["groupAtRisk"],
                        assessment["benefits"],
                        assessment["harms"],
                        assessment["mitigationStrategy"],
                    )
        if "properties" in d["modelCard"]:
            # Potentially multiple entries
            for property in d["modelCard"]["properties"]:
                self.model_card.set_property(property["name"], property["value"])

    def _cyclondex_component(self, d):
        self.cyclonedx_package.initialise()
        self.component_id = self.component_id + 1
        if d["type"] in [
            "file",
            "library",
            "application",
            "operating-system",
            "machine-learning-model",
        ]:
            package = d["name"]
            self.cyclonedx_package.set_name(package)
            if "version" in d:
                version = d["version"]
                self.cyclonedx_package.set_version(version)
            else:
                if self.debug:
                    print(f"[ERROR] Version not specified for {package}")
                version = "MISSING"
            # Record type of component
            self.cyclonedx_package.set_type(d["type"])
            # If bom-ref not present, auto generate one
            bom_ref = d.get("bom-ref", f"CycloneDX-Component-{self.component_id}")
            self.cyclonedx_package.set_value("bom-ref", bom_ref)
            if "supplier" in d:
                # Assume that this refers to an organisation
                supplier_name = d["supplier"]["name"]
                # Check for contact details (email)
                if "contact" in d["supplier"]:
                    for contact in d["supplier"]["contact"]:
                        if "email" in contact:
                            supplier_name = f'{supplier_name} ({contact["email"]})'
                self.cyclonedx_package.set_supplier("Organisation", supplier_name)
            if "author" in d:
                # Assume that this refers to an individual
                self.cyclonedx_package.set_originator("Person", d["author"])
            if "description" in d:
                self.cyclonedx_package.set_description(d["description"])
            if "hashes" in d:
                # Potentially multiple entries
                for checksum in d["hashes"]:
                    self.cyclonedx_package.set_checksum(
                        checksum["alg"].replace("SHA-", "SHA"), checksum["content"]
                    )
            license_data = None
            # Multiple ways of defining license data
            if "licenses" in d and len(d["licenses"]) > 0:
                license_data = d["licenses"][0]
            elif "evidence" in d:
                if "licenses" in d["evidence"]:
                    if len(d["evidence"]["licenses"]) > 0:
                        license_data = d["evidence"]["licenses"][0]
            if license_data is not None:
                # Multiple ways of defining licenses
                license = None
                if "license" in license_data:
                    if "id" in license_data["license"]:
                        license = license_data["license"]["id"]
                    elif "name" in license_data["license"]:
                        license = license_data["license"]["name"]
                    elif "expression" in license_data["license"]:
                        license = license_data["license"]["expression"]
                elif "expression" in license_data:
                    license = license_data["expression"]
                if license is not None:
                    # Assume License concluded is same as license declared
                    self.cyclonedx_package.set_licenseconcluded(license)
                    self.cyclonedx_package.set_licensedeclared(license)
            if "copyright" in d:
                self.cyclonedx_package.set_copyrighttext(d["copyright"])
            if "cpe" in d:
                if d["cpe"].lower().startswith("cpe:2.3"):
                    self.cyclonedx_package.set_externalreference(
                    "SECURITY", "cpe23Type", d["cpe"]
                )
                elif d["cpe"].lower().startswith("cpe:/"):
                    self.cyclonedx_package.set_externalreference(
                        "SECURITY", "cpe22Type", d["cpe"]
                    )
            if "purl" in d:
                self.cyclonedx_package.set_externalreference(
                    "PACKAGE-MANAGER", "purl", d["purl"]
                )
            if "group" in d:
                self.cyclonedx_package.set_value("group", d["group"])
            if "properties" in d:
                # Potentially multiple entries
                for property in d["properties"]:
                    self.cyclonedx_package.set_property(
                        property["name"], property["value"]
                    )
            if "externalReferences" in d:
                # Potentially multiple entries
                for reference in d["externalReferences"]:
                    ref_type = reference["type"]
                    ref_url = reference["url"]
                    # Try to map type to package element
                    if ref_type == "website":
                        self.cyclonedx_package.set_homepage(ref_url)
                    elif ref_type == "distribution":
                        self.cyclonedx_package.set_downloadlocation(ref_url)
            if "modelCard" in d:
                self._cyclonedx_mlmodel(d)
                self.cyclonedx_package.set_value(
                    "modelCard", self.model_card.get_modelcard()
                )
            # Save package metadata
            self.packages[(package, version)] = self.cyclonedx_package.get_package()
            self.id[bom_ref] = package
            # Handle component assemblies
            if "components" in d:
                for component in d["components"]:
                    self._cyclondex_component(component)

    def parse_cyclonedx_json(self, sbom_file):
        """parses CycloneDX JSON BOM file extracting package name, version and license"""
        data = json.load(open(sbom_file, "r", encoding="utf-8"))
        files = {}
        relationships = []
        # First relationship is assumed to be the root element
        relationship_type = " DESCRIBES "
        vulnerabilities = []
        cyclonedx_relationship = SBOMRelationship()
        cyclonedx_document = SBOMDocument()
        # Check valid CycloneDX JSON file (and not SPDX)
        cyclonedx_json_file = data.get("bomFormat", False)
        if cyclonedx_json_file:
            cyclonedx_version = data["specVersion"]
            cyclonedx_document.set_version(cyclonedx_version)
            cyclonedx_document.set_type("cyclonedx")
            if "metadata" in data:
                if "timestamp" in data["metadata"]:
                    cyclonedx_document.set_created(data["metadata"]["timestamp"])
                if "tools" in data["metadata"]:
                    if cyclonedx_version == "1.5":
                        if "components" in data["metadata"]["tools"]:
                            for component in data["metadata"]["tools"]["components"]:
                                name = component["name"]
                                if "version" in component:
                                    name = f'{name}#{component["version"]}'
                                cyclonedx_document.set_creator("tool", name)
                        else:
                            # This is the legacy interface which is deprecated.
                            if self.debug:
                                print("Legacy tool(s) specification still being used.")
                            name = data["metadata"]["tools"][0]["components"][0]["name"]
                            if "version" in data["metadata"]["tools"][0]["components"][0]:
                                name = f'{name}#{data["metadata"]["tools"][0]["components"][0]["version"]}'
                            cyclonedx_document.set_creator("tool", name)
                    else:
                        name = data["metadata"]["tools"][0]["name"]
                        if "version" in data["metadata"]["tools"]:
                            name = f'{name}#{data["metadata"]["tools"][0]["name"]}'
                        cyclonedx_document.set_creator("tool", name)
                if "authors" in data["metadata"]:
                    name = ""
                    if "name" in data["metadata"]["authors"]:
                        name = data["metadata"]["authors"][0]["name"]
                    if "email" in data["metadata"]["authors"]:
                        name = f'{name}#{data["metadata"]["authors"][0]["email"]}'
                    cyclonedx_document.set_creator("person", name)
                if "component" in data["metadata"]:
                    component_name = data["metadata"]["component"]["name"]
                    cyclonedx_document.set_name(component_name)
                    component_type = data["metadata"]["component"]["type"]
                    cyclonedx_document.set_metadata_type(component_type)
                    if "bom-ref" in data["metadata"]["component"]:
                        bom_ref = data["metadata"]["component"]["bom-ref"]
                        cyclonedx_document.set_value("bom-ref", bom_ref)
                    else:
                        bom_ref = "CylconeDX-Component-0000"
                    self.id[bom_ref] = component_name
                    if "version" in data["metadata"]["component"]:
                        component_version = data["metadata"]["component"]["version"]
                        cyclonedx_document.set_value(
                            "metadata_version", component_version
                        )
            if "components" in data:
                for d in data["components"]:
                    self._cyclondex_component(d)
            if "dependencies" in data:
                for d in data["dependencies"]:
                    source_id = d["ref"]
                    # Get source name
                    source = None
                    if source_id in self.id:
                        source = self.id[source_id]
                    elif self.debug:
                        print(f"[ERROR] Unable to find {source_id}")
                    if source is not None and d.get("dependsOn") is not None:
                        for target_id in d["dependsOn"]:
                            if target_id in self.id:
                                target = self.id[target_id]
                                cyclonedx_relationship.initialise()
                                cyclonedx_relationship.set_relationship(
                                    source, relationship_type, target
                                )
                                cyclonedx_relationship.set_relationship_id(
                                    source_id, target_id
                                )
                                relationships.append(
                                    cyclonedx_relationship.get_relationship()
                                )
                            elif self.debug:
                                print(f"[ERROR] Unable to find {target_id}")
                    relationship_type = " DEPENDS_ON "
            if "vulnerabilities" in data:
                vuln_info = Vulnerability(validation="cyclonedx")
                for vuln in data["vulnerabilities"]:
                    vuln_info.initialise()
                    if "bom-ref" in vuln:
                        vuln_info.set_value("bom-ref", vuln["bom-ref"])
                    vuln_info.set_id(vuln["id"])
                    if "source" in vuln:
                        vuln_info.set_value("source-name", vuln["source"]["name"])
                        vuln_info.set_value("source-url", vuln["source"]["url"])
                    if "description" in vuln:
                        vuln_info.set_description(vuln["description"])
                    if "created" in vuln:
                        vuln_info.set_value("created", vuln["created"])
                    if "analysis" in vuln:
                        if "state" in vuln["analysis"]:
                            vuln_info.set_value("status", vuln["analysis"]["state"])
                        if "detail" in vuln["analysis"]:
                            vuln_info.set_comment(vuln["analysis"]["detail"])
                        if "justification" in vuln["analysis"]:
                            vuln_info.set_value(
                                "justification", vuln["analysis"]["justification"]
                            )
                    vulnerabilities.append(vuln_info.get_vulnerability())
                if self.debug:
                    print(vulnerabilities)
        return cyclonedx_document, files, self.packages, relationships, vulnerabilities

    def _parse_component(self, component_element):
        """Parses a CycloneDX component element and returns a dictionary of its contents."""
        component = {}
        # Get the attributes of the component element.
        attributes = component_element.attrib
        # Add the attributes to the component dictionary.
        for attribute in attributes:
            component[attribute] = attributes[attribute]
        # Get the child elements of the component element.
        children = component_element.getchildren()
        # Iterate over the child elements of the component element.
        for child in children:
            # Get the tag name and text of the child element.
            tag = child.tag
            component[tag] = self._parse_dependencies(child)
        return component

    def parse_document_xml(self):
        cyclonedx_document = SBOMDocument()
        # Extract CycloneDX version from schema
        cyclonedx_version = self.schema.replace("}", "").split("/")[-1]
        cyclonedx_document.set_version(cyclonedx_version)
        cyclonedx_document.set_type("cyclonedx")
        component_name = None
        bom_ref = None

        for metadata in self.root.findall(self.schema + "metadata"):
            timestamp = self._xml_component(metadata, "timestamp")
            if timestamp != "":
                cyclonedx_document.set_created(timestamp)
            for tools in metadata.findall(self.schema + "tools"):
                for tool in tools.findall(self.schema + "tool"):
                    name = self._xml_component(tool, "name")
                    version = self._xml_component(tool, "version")
                    cyclonedx_document.set_creator("tool", f"{name}#{version}")
            for authors in metadata.findall(self.schema + "authors"):
                for author in authors.findall(self.schema + "author"):
                    name = self._xml_component(author, "name")
                    email = self._xml_component(author, "email")
                    if email != "":
                        name = f"{name}#{email}"
                    cyclonedx_document.set_creator("person", name)
            for component in metadata.findall(self.schema + "component"):
                component_name = self._xml_component(component, "name")
                attrib = component.attrib
                bom_ref = attrib.get("bom-ref")
                cyclonedx_document.set_name(component_name)
            if component_name is not None and bom_ref is not None:
                cyclonedx_document.set_value("bom-ref", bom_ref)
                self.id[bom_ref] = component_name
        return cyclonedx_document

    def _xml_component(self, item, element):
        data = item.find(self.schema + element)
        if data is not None:
            return data.text.strip()
        return ""

    def _parse_component_xml(self, component):
        self.cyclonedx_package.initialise()
        self.component_id = self.component_id + 1
        # Record type of component
        self.cyclonedx_package.set_type(component.attrib["type"])
        package = self._xml_component(component, "name")
        version = self._xml_component(component, "version")
        self.cyclonedx_package.set_name(package)
        self.cyclonedx_package.set_version(version)
        attrib = component.attrib
        bom_ref = attrib.get("bom-ref")
        if bom_ref is None:
            bom_ref = f"CycloneDX-Component-{self.component_id}"
        self.cyclonedx_package.set_value("bom-ref", bom_ref)
        for supplier in component.findall(self.schema + "supplier"):
            supplier_name = self._xml_component(supplier, "name")
            for element in supplier.findall(self.schema + "contact"):
                email = self._xml_component(element, "email")
                if email != "":
                    # contact_name = self._xml_component(element, "name")
                    supplier_name = f"{supplier_name} ({email})"
                    break
            self.cyclonedx_package.set_supplier("Organisation", supplier_name)
        author = self._xml_component(component, "author")
        if author != "":
            # Assume that this refers to an individual
            self.cyclonedx_package.set_originator("Person", author)
        description = self._xml_component(component, "description")
        if description != "":
            self.cyclonedx_package.set_copyrighttext(description)
        for hashes in component.findall(self.schema + "hashes"):
            for hash in hashes.findall(self.schema + "hash"):
                self.cyclonedx_package.set_checksum(str(hash.attrib["alg"]), hash.text)
        for licenses in component.findall(self.schema + "licenses"):
            for license in licenses.findall(self.schema + "license"):
                # Multiple ways of defining license data
                license_id = self._xml_component(licenses, "expression")
                if license_id == "":
                    license_id = self._xml_component(license, "id")
                    if license_id == "":
                        license_id = self._xml_component(license, "name")
                if license_id != "":
                    # Assume License concluded is same as license declared
                    self.cyclonedx_package.set_licenseconcluded(license_id)
                    self.cyclonedx_package.set_licensedeclared(license_id)
        copyright = self._xml_component(component, "copyright")
        if copyright != "":
            self.cyclonedx_package.set_copyrighttext(copyright)
        cpe = self._xml_component(component, "cpe")
        if cpe != "":
            if cpe.lower().startswith("cpe:2.3"):
                self.cyclonedx_package.set_externalreference(
                    "SECURITY", "cpe23Type", cpe
                )
            elif cpe.lower().startswith("cpe:/"):
                self.cyclonedx_package.set_externalreference(
                    "SECURITY", "cpe22Type", cpe
                )
        purl = self._xml_component(component, "purl")
        if purl != "":
            self.cyclonedx_package.set_externalreference(
                "PACKAGE-MANAGER", "purl", purl
            )
        # Potentially multiple entries
        for properties in component.findall(self.schema + "properties"):
            for property in properties.findall(self.schema + "property"):
                params = property.attrib
                # Handle different ways of specifying property
                if params.get("value") is not None:
                    # Explicit value specified as attribute
                    self.cyclonedx_package.set_property(params["name"], params["value"])
                else:
                    # Implicit value
                    self.cyclonedx_package.set_property(params["name"], property.text)
        for references in component.findall(self.schema + "externalReferences"):
            for reference in references.findall(self.schema + "reference"):
                params = reference.attrib
                ref_type = params.get("type")
                ref_url = self._xml_component(reference, "url")
                # Try to map type to package element
                if ref_type == "website":
                    self.cyclonedx_package.set_homepage(ref_url)
                elif ref_type == "distribution":
                    self.cyclonedx_package.set_downloadlocation(ref_url)

        # Save package metadata
        self.packages[(package, version)] = self.cyclonedx_package.get_package()
        self.id[bom_ref] = package
        # Handle component assembly
        for components in component.findall(self.schema + "components"):
            for component_assembly in components.findall(self.schema + "component"):
                self._parse_component_xml(component_assembly)

    def parse_components_xml(self):
        for components in self.root.findall(self.schema + "components"):
            for component in components.findall(self.schema + "component"):
                self._parse_component_xml(component)

    def parse_dependencies_xml(self):
        relationships = []
        cyclonedx_relationship = SBOMRelationship()
        # First relationship is assumed to be the root element
        relationship_type = " DESCRIBES "
        for dependency in self.root.findall(self.schema + "dependencies"):
            for depends in dependency.findall(self.schema + "dependency"):
                source = depends.attrib["ref"]
                source_id = self.id[source]
                for depend in depends.findall(self.schema + "dependency"):
                    # Get ids
                    target_id = self.id[depend.attrib["ref"]]
                    cyclonedx_relationship.initialise()
                    cyclonedx_relationship.set_relationship(
                        source_id, relationship_type, target_id
                    )
                    cyclonedx_relationship.set_relationship_id(
                        source, depend.attrib["ref"]
                    )
                    relationships.append(cyclonedx_relationship.get_relationship())
                    relationship_type = " DEPENDS_ON "
        return relationships

    def parse_vulnerabilities_xml(self):
        # TODO
        vulnerabilities = []
        return vulnerabilities

    def parse_cyclonedx_xml(self, sbom_file):
        self.tree = ET.parse(sbom_file)
        self.root = self.tree.getroot()
        # Extract schema
        self.schema = self.root.tag[: self.root.tag.find("}") + 1]
        document = self.parse_document_xml()
        self.parse_components_xml()
        dependencies = self.parse_dependencies_xml()
        vulnerabilities = self.parse_vulnerabilities_xml()
        return document, {}, self.packages, dependencies, vulnerabilities
