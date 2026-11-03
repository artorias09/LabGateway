import argparse
import getpass
from core import safe_slug
import store

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    create=sub.add_parser('create-user')
    create.add_argument('username')
    create.add_argument('role',choices=['teacher','student'])
    args=parser.parse_args()
    store.init()
    if args.command=='create-user':
        if not safe_slug(args.username):
            parser.error('Nome: 3-32 caracteres, minúsculas, letras/números/_/-')
        password=getpass.getpass('Senha (mínimo 12 caracteres): ')
        store.create_user(args.username,password,args.role)
        print('Conta criada:',args.username,args.role)

if __name__=='__main__':
    main()
