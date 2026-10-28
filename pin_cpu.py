'''Pin one serial process or MPI rank to a CPU inside its inherited Linux mask.'''
import argparse
import json
import os
import platform
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpus',required=True)
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args()
    cpus=[int(cpu) for cpu in args.cpus.split(',')]
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    rank=int(os.environ.get('OMPI_COMM_WORLD_RANK','0'))
    if not command or len(set(cpus))!=len(cpus) or not 0<=rank<len(cpus):
        parser.error('Invalid command, CPU list or MPI rank')
    cpu=cpus[rank]
    if cpu not in os.sched_getaffinity(0):
        raise RuntimeError('Requested CPU is outside inherited affinity')
    os.sched_setaffinity(0,{cpu})
    mask=sorted(os.sched_getaffinity(0))
    if mask!=[cpu]:
        raise RuntimeError('Failed to set affinity')
    message='AB_AFFINITY '+json.dumps(dict(rank=rank,host=platform.node(),cpus=mask))+'\n'
    os.write(2,message.encode('utf-8'))
    os.execv(command[0],command)


if __name__=='__main__':
    main()
