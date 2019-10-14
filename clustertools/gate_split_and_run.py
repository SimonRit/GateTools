#!/usr/bin/env python

import os
import tempfile
import shutil
import click
import socket
import subprocess
import colorama
import numpy as np
import sys

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

from parserMacro import *


def get_dns_domain():
    return socket.getfqdn().split('.', 1)[1]

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.command(context_settings=CONTEXT_SETTINGS)
@click.argument('mac', nargs=1)
@click.option('-j', '--jobs', default=1, help='Number of jobs/core')
@click.option('--splittime', is_flag=True, help='Divide time duration into the number of jobs')
@click.option('-o', '--output', default='', help='Output folder path (default: run.XXX)')
@click.option('-a', '--alias', type=(str, str), multiple=True, help='Alias (-a stringExemple Lu-177 -a valueExample 72.3 -a oneDifferentAliasForEachJobExample 1,2.5,3,4)')
@click.option('--copydata', is_flag=True, help='Hard copy data into run.XXX folder (default: symbolic link)')
@click.option('-d', '--dry', is_flag=True, help='If dry is set, copy all files, write the submission command lines but do not execute them')
@click.option('--qt', is_flag=True, help='Add visualisation - Be sure to have few particles')
@click.option('--env', default='', help='Bash script to set environment variables during job. This file is source at the beginning.')
@click.option('--jobfile', default='', help='Job file for the cluster allowing to modify submission parameters (--jobfile="current" display the path of the current job file and exit)')
def runJobs(mac, jobs, env, splittime, output, alias, copydata, dry, qt, jobfile):
    """
    \b
    Run Gate jobs

    MAC: input mac filename

    """

    directoryJobFiles = os.path.dirname(os.path.realpath(__file__))

    # Source env file
    envCommand = ''
    if not env == '':
        if not os.path.isabs(env):
          env = os.path.join(os.getcwd(), env)
        if not os.path.isfile(env):
            print(colorama.Fore.RED + 'ERROR: No env found : ' + env + colorama.Style.RESET_ALL)
            exit(1)
        else:
            envCommand = env
    else:
        envCommand = 'NONE'

    jobFile = ""
    # Take the correct job file according to the cluster name and jobfile option
    if jobfile == '' or jobfile == "current":
        if get_dns_domain() == 'in2p3.fr':
            jobFile = os.path.join(directoryJobFiles, 'gate_job_ccin2p3.job')
        elif get_dns_domain() == 'idris.fr':
            jobFile = os.path.join(directoryJobFiles, 'gate_job_idris.slurm')
        else:
            jobFile = os.path.join(directoryJobFiles, 'gate_job_cluster.job')
        if not os.path.isfile(jobFile):
            print(colorama.Fore.RED + 'ERROR: The job file does not exist: ' + jobFile + colorama.Style.RESET_ALL)
            exit(1)
        if jobfile == "current":
            print(colorama.Fore.GREEN + 'Path to the job file: ' + colorama.Style.RESET_ALL)
            print(jobFile)
            exit(1)
    else:
        jobFile = jobfile
        if not os.path.isabs(jobFile):
          jobFile = os.path.join(os.getcwd(), jobFile)
        if not os.path.isfile(jobFile):
            print(colorama.Fore.RED + 'ERROR: The job file does not exist: ' + jobFile + colorama.Style.RESET_ALL)
            exit(1)

    # Get the release of Gate used for the simulation using the env file if present
    try:
        bashCommand = ""
        if not env == '':
            bashCommand = "source " + env + "; which Gate"
        else:
            bashCommand = "which Gate"
        outputCommand = subprocess.check_output(['bash','-c', bashCommand])
        releasedir = outputCommand[:-1].decode('utf-8')
    except:
        print(colorama.Fore.RED + 'ERROR: No Gate found in PATH' + colorama.Style.RESET_ALL)
        exit(1)
    else:
        print('Found Gate in folder: ' + releasedir)
        releasedir = 'NONE'

    # Get macro folder and files
    fullMacroDir = os.path.join(os.getcwd(), os.path.dirname(os.path.dirname(mac)))
    relativeMacroDir = os.path.dirname(os.path.dirname(mac))
    mainMacroFile = mac[len(relativeMacroDir)+1:]
    if relativeMacroDir == '':
        relativeMacroDir = '.'
        mainMacroFile = mac
    if not os.path.isdir(os.path.join(fullMacroDir, 'mac')):
        print(colorama.Fore.RED + 'ERROR: The mac folder does not exist: ' + os.path.join(fullMacroDir, 'mac') + colorama.Style.RESET_ALL)
        exit(1)
    if not os.path.isdir(os.path.join(fullMacroDir, 'data')):
        print(colorama.Fore.RED + 'ERROR: The data folder does not exist: ' + os.path.join(fullMacroDir, 'data') + colorama.Style.RESET_ALL)
        exit(1)
    if not os.path.isfile(mac):
        print(colorama.Fore.RED + 'ERROR: The mac file does not exist: ' + mac + colorama.Style.RESET_ALL)
        exit(1)

    # Check output path is absolute or relative
    outputDir = output
    if not outputDir == '' and not os.path.isabs(outputDir):
      outputDir = os.path.join(os.getcwd(), outputDir)
    # Create output directory
    if not outputDir == '' and os.path.isdir(outputDir):
        print(colorama.Fore.YELLOW + 'WARNING: The output folder already exist: ' + outputDir + colorama.Style.RESET_ALL)
        print(colorama.Fore.YELLOW + 'Evereything will be overwritten' + colorama.Style.RESET_ALL)
    if outputDir == '':
        outputDir = tempfile.mkdtemp(prefix='run.', dir=fullMacroDir)
    elif not os.path.isdir(outputDir):
        os.makedirs(outputDir)
    runId = os.path.basename(outputDir)[os.path.basename(outputDir).find('.') +1:]
    if runId == '':
        runId == os.path.basename(outputDir)
    print('Run Id is: ' + runId)

    # Find qsub
    qsub = shutil.which('qsub')
    if qsub is None:
        qsub = shutil.which('sbatch')
        if qsub is None:
            print('No qsub, run Gate on multiple cores.')

    # Parameter files
    paramFileName = os.path.join(outputDir, 'run.log')
    paramFile = open(paramFileName, "w")
    paramFile.write('number of jobs = ' + str(jobs) + '\n')
    paramFile.write('macro = ' + mac + '\n')
    paramFile.write('runId = ' + runId + '\n')

    #Parse macro files and sub-Macro
    os.makedirs(os.path.join(outputDir, 'mac'), exist_ok=True)
    parserMacro = ParserMacro()
    for a in alias:
        if ',' in a[1]:
            parserMacro.setAlias((a[0], a[1].split(",")), jobs)
        else:
            parserMacro.setAlias(a, jobs)
    parserMacro.setAlias(("JOB_ID", list(range(0, jobs))), jobs)
    parserMacro.parseMainMacFiles(fullMacroDir, mainMacroFile)
    paramtogate = ''
    if qt:
        print(colorama.Fore.YELLOW + 'WARNING: Be sure to have few particles for visualisation' + colorama.Style.RESET_ALL)
        parserMacro.setVisualisation()
        paramtogate += ' --qt '

    # Copy data
    if copydata:
        shutil.copytree(os.path.join(fullMacroDir, 'data'), os.path.join(outputDir, 'data'))
    else:
        if os.path.islink(os.path.join(outputDir, 'data')):
            os.unlink(os.path.join(outputDir, 'data'))
        elif os.path.isdir(os.path.join(outputDir, 'data')):
            shutil.rmtree(os.path.join(outputDir, 'data'))
        os.symlink(os.path.join(fullMacroDir, 'data'), os.path.join(outputDir, 'data'))

    #Manage split time option
    #Divide the time into jobs range of time
    if splittime:
        startTime = float(parserMacro.getAttributes('setTimeStart')[0])
        stopTime = float(parserMacro.getAttributes('setTimeStop')[0])
        slicedTime = (stopTime - startTime)/jobs
        arrayStartTime = []
        arrayStopTime = []
        for i in range(0, jobs):
            arrayStartTime += [startTime + i*slicedTime]
            arrayStopTime += [startTime + (i+1)*slicedTime]
        parserMacro.setAttributes('setTimeStart', arrayStartTime)
        parserMacro.setAttributes('setTimeSlice', np.array(arrayStopTime) - np.array(arrayStartTime))
        parserMacro.setAttributes('setTimeStop', arrayStopTime)

    #Write mac files into output folder
    parserMacro.writeMacFiles(outputDir)

    #Create file to write commands in it
    paramFile.write('\ncommands: \n')

    # Run jobs
    for i in range(0, jobs):
        #Set paramtogate with alias for each job
        paramtogateJob = paramtogate + ' -a [JOB_ID,' + str(i) + ']'
        for aliasMac in parserMacro.aliasToGate:
            paramtogateJob += '[' + aliasMac + ',' + str(parserMacro.aliasToGate[aliasMac][i]) + ']'

        if get_dns_domain() == 'in2p3.fr':
            command = 'qsub -o ' + outputDir + \
                      ' -e ' + outputDir + \
                      ' -l sps=1 -N \"gate.' + runId + \
                      '\" -v \"PARAM=\\\"' + paramtogateJob + \
                      '\\\",INDEX=' + str(i) + \
                      ',INDEXMAX=' + str(jobs) + \
                      ',OUTPUTDIR=' + outputDir + \
                      ',RELEASEDIR=' + releasedir + \
                      ',MACROFILE=' + os.path.join(outputDir, mainMacroFile) + \
                      ',MACRODIR=' + outputDir + \
                      ',ENV=' + envCommand + \
                      '\" ' + jobFile
        elif get_dns_domain() == 'idris.fr':
            command = 'sbatch -o ' + outputDir + \
                      ' -e ' + outputDir + \
                      ' -l sps=1 -J \"gate.' + runId + \
                      ' --export=ALL,\"PARAM=\\\"' + paramtogateJob + \
                      '\\\",INDEX=' + str(i) + \
                      ',INDEXMAX=' + str(jobs) + \
                      ',OUTPUTDIR=' + outputDir + \
                      ',RELEASEDIR=' + releasedir + \
                      ',MACROFILE=' + os.path.join(outputDir, mainMacroFile) + \
                      ',MACRODIR=' + outputDir + \
                      ',ENV=' + envCommand + \
                      '\" ' + jobFile
        elif qsub is None:
            command = 'PARAM=\" ' + paramtogateJob + \
                      '\" INDEX=' + str(i) + \
                      ' INDEXMAX=' + str(jobs) + \
                      ' OUTPUTDIR=' + outputDir + \
                      ' RELEASEDIR=' + releasedir + \
                      ' MACROFILE=' + os.path.join(outputDir, mainMacroFile) + \
                      ' MACRODIR=' + outputDir + \
                      ' ENV=' + envCommand + \
                      ' PBS_JOBID=\"local_' + str(i) + \
                      '\" bash ' + jobFile + " &>  " + os.path.join(outputDir, "gate.o_" + str(i)) + " &"
        else:
            command = 'qsub -N \"gatejob.' + runId + \
                      ' -o ' + outputDir + \
                      ' -v \"PARAM=\\\"' + paramtogateJob + \
                      '\\\",INDEX=' + str(i) + \
                      ',INDEXMAX=' + str(jobs) + \
                      ',OUTPUTDIR=' + outputDir + \
                      ',RELEASEDIR=' + releasedir + \
                      ',MACROFILE=' + os.path.join(outputDir, mainMacroFile) + \
                      ',MACRODIR=' + outputDir + \
                      ',ENV=' + envCommand + \
                      '\" ' + jobFile
        paramFile.write(command)
        paramFile.write("\n")
        if dry:
            print(command)
        else:
            os.system(command)

    paramFile.close()
    print(str(jobs) + ' jobs running')
    print('Run folder is: ' + outputDir)


if __name__ == "__main__":
    colorama.init()
    runJobs()
