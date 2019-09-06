# Copyright (c) 2013, 2014-2019 Oracle and/or its affiliates. All rights reserved.


"""Provide Module Description
"""

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
__author__ = ["Andrew Hopkinson (Oracle Cloud Solutions A-Team)"]
__copyright__ = "Copyright (c) 2013, 2014-2019  Oracle and/or its affiliates. All rights reserved."
__version__ = "1.0.0.0"
__date__ = "@BUILDDATE@"
__status__ = "@RELEASE@"
__module__ = "okitWebDesigner"
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import oci
import json
import os
import shutil
import tempfile
import time
import urllib

from flask import Blueprint
from flask import redirect
from flask import render_template
from flask import request
from flask import send_file
from flask import send_from_directory
from flask import session
from flask import url_for

from common.ociCommon import logJson
from common.ociCommon import standardiseIds
from common.ociQuery import executeQuery
from generators.ociTerraformGenerator import OCITerraformGenerator
from generators.ociTerraform11Generator import OCITerraform11Generator
from generators.ociResourceManagerGenerator import OCIResourceManagerGenerator
from generators.ociAnsibleGenerator import OCIAnsibleGenerator
from generators.ociPythonGenerator import OCIPythonGenerator
from facades.ociCompartment import OCICompartments
from facades.ociVirtualCloudNetwork import OCIVirtualCloudNetworks
from facades.ociInternetGateway import OCIInternetGateways
from facades.ociRouteTable import OCIRouteTables
from facades.ociSecurityList import OCISecurityLists
from facades.ociSubnet import OCISubnets
from facades.ociLoadBalancer import OCILoadBalancers
from facades.ociInstance import OCIInstances
from facades.ociInstance import OCIInstanceVnics
from facades.ociResourceManager import OCIResourceManagers

from common.ociLogging import getLogger

# Configure logging
logger = getLogger()

bp = Blueprint('okit', __name__, url_prefix='/okit', static_folder='static/okit')

debug_mode = bool(str(os.getenv('DEBUG_MODE', 'False')).title())
template_root = '/okit/visualiser/templates'


def standardiseJson(json_data={}, **kwargs):
    logJson(json_data)
    json_data = standardiseIds(json_data)
    logJson(json_data)
    return json_data


@bp.route('/designer', methods=(['GET', 'POST']))
def designer():
    oci_assets_js = os.listdir(os.path.join(bp.static_folder, 'js', 'oci_assets'))
    palette_icons_svg = os.listdir(os.path.join(bp.static_folder, 'palette'))
    palette_icons = []
    for palette_svg in sorted(palette_icons_svg):
        palette_icon = {'svg': palette_svg}
        palette_icon['title'] = palette_svg.split('.')[0].replace('_', ' ')
        palette_icons.append(palette_icon)
    logger.info('Palette Icons : {0!s:s}'.format(palette_icons))
    if request.method == 'POST':
        request_json = {}
        response_json = {}
        for key, value in request.form.items():
            request_json[key] = value
        request_json['virtual_cloud_network_filter'] = {'display_name': request_json.get('virtual_cloud_network_name_filter', '')}
        logger.info('Request Json {0!s:s}'.format(request_json))
        #response_json = executeQuery(request_json)
        logJson(response_json)
        response_string = json.dumps(response_json, separators=(',', ': '))
        return render_template('okit/designer.html', oci_assets_js=oci_assets_js, palette_icons=palette_icons, okit_query_request_json=request_json, okit_query_response_json=response_string)
    elif request.method == 'GET':
        return render_template('okit/designer.html', oci_assets_js=oci_assets_js, palette_icons=palette_icons)


@bp.route('/propertysheets/<string:sheet>', methods=(['GET']))
def propertysheets(sheet):
    return render_template('okit/propertysheets/{0:s}'.format(sheet))


@bp.route('/generate/<string:language>', methods=(['GET', 'POST']))
def generate(language):
    logger.info('Language : {0:s} - {1:s}'.format(str(language), str(request.method)))
    logger.info('JSON     : {0:s}'.format(str(request.json)))
    if request.method == 'POST':
        try:
            destination_dir = tempfile.mkdtemp();
            if language == 'terraform':
                generator = OCITerraformGenerator(template_root, destination_dir, request.json)
            elif language == 'ansible':
                generator = OCIAnsibleGenerator(template_root, destination_dir, request.json)
            elif language == 'terraform11':
                generator = OCITerraform11Generator(template_root, destination_dir, request.json)
            generator.generate()
            generator.writeFiles()
            zipname = generator.createZipArchive(os.path.join(destination_dir, language), "/tmp/okit-{0:s}".format(str(language)))
            logger.info('Zipfile : {0:s}'.format(str(zipname)))
            shutil.rmtree(destination_dir)
            filename = os.path.split(zipname)
            logger.info('Split Zipfile : {0:s}'.format(str(filename)))
            return zipname
            #return send_file(zipname, mimetype='application/zip', as_attachment=True)
            #return send_from_directory(filename[0], filename[-1], mimetype='application/zip', as_attachment=True)
        except Exception as e:
            logger.exception(e)
            return str(e), 500
    else:
        return send_from_directory('/tmp', "okit-{0:s}.zip".format(str(language)), mimetype='application/zip', as_attachment=True)


@bp.route('/oci/compartment', methods=(['GET']))
def ociCompartment():
    ociCompartments = OCICompartments()
    compartments = ociCompartments.listTenancy()
    #logger.info("Compartments: {0!s:s}".format(compartments))
    return json.dumps(compartments, sort_keys=False, indent=2, separators=(',', ': '))


@bp.route('/oci/query/<string:cloud>', methods=(['GET', 'POST']))
def ociQuery(cloud):
    if cloud == 'oci':
        if request.method == 'POST':
            response_json = {}
            logger.info('Post JSON : {0:s}'.format(str(request.json)))
            return executeQuery(request.json)
        else:
            ociCompartments = OCICompartments()
            compartments = ociCompartments.listTenancy()
            return render_template('okit/oci_query.html', compartments=compartments)
    else:
        return '404'


@bp.route('/oci/artifacts/<string:artifact>', methods=(['GET']))
def ociArtifacts(artifact):
    logger.info('Artifact : {0:s}'.format(str(artifact)))
    query_string = request.query_string
    parsed_query_string = urllib.parse.unquote(query_string.decode())
    query_json = standardiseIds(json.loads(parsed_query_string), from_char='-', to_char='.')
    logJson(query_json)
    logger.info(json.dumps(query_json, sort_keys=True, indent=2, separators=(',', ': ')))
    response_json = {}
    if artifact == 'Compartment':
        logger.info('---- Processing Compartments')
        oci_compartments = OCICompartments()
        #response_json = oci_compartments.list(filter=query_json.get('compartment_filter', None))
        response_json = oci_compartments.get(compartment_id=query_json['compartment_id'])
    elif artifact == 'VirtualCloudNetwork':
        logger.info('---- Processing Virtual Cloud Networks')
        oci_virtual_cloud_networks = OCIVirtualCloudNetworks(compartment_id=query_json['compartment_id'])
        response_json = oci_virtual_cloud_networks.list(filter=query_json.get('virtual_cloud_network_filter', None))
    elif artifact == 'InternetGateway':
        logger.info('---- Processing Internet Gateways')
        oci_internet_gateways = OCIInternetGateways(compartment_id=query_json['compartment_id'], vcn_id=query_json['vcn_id'])
        response_json = oci_internet_gateways.list(filter=query_json.get('internet_gateway_filter', None))
    elif artifact == 'RouteTable':
        logger.info('---- Processing Route Tables')
        oci_route_tables = OCIRouteTables(compartment_id=query_json['compartment_id'], vcn_id=query_json['vcn_id'])
        response_json = oci_route_tables.list(filter=query_json.get('route_table_filter', None))
    elif artifact == 'SecurityList':
        logger.info('---- Processing Security Lists')
        oci_security_lists = OCISecurityLists(compartment_id=query_json['compartment_id'], vcn_id=query_json['vcn_id'])
        response_json = oci_security_lists.list(filter=query_json.get('security_list_filter', None))
    elif artifact == 'Subnet':
        logger.info('---- Processing Subnets')
        oci_subnets = OCISubnets(compartment_id=query_json['compartment_id'], vcn_id=query_json['vcn_id'])
        response_json = oci_subnets.list(filter=query_json.get('subnet_filter', None))
    elif artifact == 'Instance':
        logger.info('---- Processing Instances')
        oci_instances = OCIInstances(compartment_id=query_json['compartment_id'])
        instance_json = oci_instances.list(filter=query_json.get('instance_filter', None))
        oci_instance_vnics = OCIInstanceVnics(compartment_id=query_json['compartment_id'])
        response_json = []
        for instance in instance_json:
            instance['vnics'] = oci_instance_vnics.list(instance_id=instance['id'])
            instance['subnet_id'] = instance['vnics'][0]['subnet_id'] if len(instance['vnics']) > 0 else ''
            if query_json['subnet_id'] in [vnic['subnet_id'] for vnic in instance['vnics']]:
                response_json.append(instance)
    elif artifact == 'LoadBalancer':
        logger.info('---- Processing Load Balancers')
        oci_load_balancers = OCILoadBalancers(compartment_id=query_json['compartment_id'])
        response_json = oci_load_balancers.list(filter=query_json.get('load_balancer_filter', None))
        response_json = [lb for lb in response_json if query_json['subnet_id'] in lb['subnet_ids']]
    else:
        return '404'

    logger.debug(json.dumps(response_json, sort_keys=True, indent=2, separators=(',', ': ')))
    return json.dumps(standardiseIds(response_json), sort_keys=True)


@bp.route('/export/<string:destination>', methods=(['POST']))
def export(destination):
    logger.info('Destination : {0:s} - {1:s}'.format(str(destination), str(request.method)))
    logger.info('JSON     : {0:s}'.format(str(request.json)))
    if request.method == 'POST':
        try:
            destination_dir = tempfile.mkdtemp();
            stack = {}
            stack['display_name'] = 'okit-stack-export-{0!s:s}'.format(time.strftime('%Y%m%d%H%M%S'))
            stack['display_name'] = 'nightmare-stack-{0!s:s}'.format(time.strftime('%Y%m%d%H%M%S'))
            if destination == 'resourcemanager':
                # Get Compartment Information
                export_compartment_index = request.json['open_compartment_index']
                export_compartment_name = request.json['compartments'][export_compartment_index]['name']
                oci_compartments = OCICompartments()
                compartments = oci_compartments.listTenancy(filter={'name': export_compartment_name})
                # If we find a compartment
                if len(compartments) > 0:
                    # Generate Resource Manager Terraform zip
                    generator = OCIResourceManagerGenerator(template_root, destination_dir, request.json,
                                                            tenancy_ocid=oci_compartments.config['tenancy'],
                                                            region=oci_compartments.config['region'],
                                                            compartment_ocid=compartments[0]['id'])
                    generator.generate()
                    generator.writeFiles()
                    zipname = generator.createZipArchive(os.path.join(destination_dir, 'resource-manager'), "/tmp/okit-resource-manager")
                    logger.info('Zipfile : {0:s}'.format(str(zipname)))
                    # Upload to Resource manager
                    stack['compartment_id'] = compartments[0]['id']
                    stack['zipfile'] = zipname
                    stack['variables'] = generator.getVariables()
                    resource_manager = OCIResourceManagers(compartment_id=compartments[0]['id'])
                    stack_json = resource_manager.createStack(stack)
                    resource_manager.createJob(stack_json)
                    return_code = 200
                else:
                    return_code = 400
            shutil.rmtree(destination_dir)
            return stack['display_name'], return_code
        except Exception as e:
            logger.exception(e)
            return str(e), 500
    return
