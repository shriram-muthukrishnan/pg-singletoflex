"""
src/DockerImageBuilder/build_dev.py
Script to handle building dev images of Meru data-plane applications.
"""

from argparse import ArgumentParser
from ast import dump
import subprocess
from subprocess import PIPE,Popen
import shutil
from getpass import getpass
import os
import psycopg2

def main():
    """
    The top-level function of the script that takes the args, builds the
    images and updates the Application files for orcasql-breadth.
    """
    options = process_arguments()
    if (not check_connectivity(options) or not check_connectivity(options,False)):
        print("Connectivity to Source or Target Server Failed. Please check your Network Connectivity")
        return
    if not (check_if_db_exists(options)):
        print("One of the Passed in Databases does not exist on the Source Server")
        return
    dumpfile_directory = make_dump_directory()
    if not (os.path.exists(dumpfile_directory)):
        print("Dump Files Directory did not get created successfully")
        return
    all_roles_dumpfile = dump_roles(options,dumpfile_directory)
    if not (os.path.exists(all_roles_dumpfile)):
        print("Global Roles Dump did not happen successfully.")
        return
    if not remove_unwanted_users_from_cluster_dump(options, all_roles_dumpfile):
        return
    if not dump_grant_statments_perdb(options,dumpfile_directory):
        return 
    num_dbs = len(options.get("dbs"))
    num_files = len(os.listdir(dumpfile_directory))
    if(num_files != num_dbs*2 + 1):
        print("\n")
        print("Per Database Role and Schema Dump did not happen successfully")
        print("\n")
        return
    if not(change_admin_role_grants_perdb(options,dumpfile_directory)):
        print("\n")
        print("Per Database Role Dump File not Massaged successfully")
        print("\n")
        return
    if not(create_global_roles_ontarget(options,all_roles_dumpfile)):
        print("\n")
        print("Failed when creating Global Roles on Target server Cluster")
        print("\n")
        return
    if not(run_grants_per_db(options,dumpfile_directory)):
        print("\n")
        print("Failed when running GRANT/REVOKE statements on target server")
        print("\n")
        return
    print("####################################################################################################")
    print("\n")
    print("                                         SUCCESS                                                    ")
    print("\n")
    print("####################################################################################################")

def make_dump_directory():
    try: 
        curr_wd = os.getcwd()
        dumpfile_directory = os.path.join(curr_wd, "dump_files") 
        if (os.path.exists(dumpfile_directory)):
            shutil.rmtree(dumpfile_directory)
        os.mkdir(dumpfile_directory)
        return dumpfile_directory
    except OSError as error:
        print(error)  

def dump_roles(options_dict, dumpfile_directory):
    all_roles_dumpfile = os.path.join(dumpfile_directory, "all_roles.sql")
    os.environ["PGPASSWORD"] = options_dict.get("source_password")
    command = 'pg_dumpall -h {0} -U {1} -p {2} -r -f {3}'\
    .format(options_dict.get("source_fqdn"),options_dict.get("source_adminuser"),options_dict.get("source_pg_port"),all_roles_dumpfile)
    print("\n")
    print("-----------------Dumping All Roles----------------------")
    print("\n")
    p = Popen(command,shell=True,stdin=PIPE,stdout=PIPE,stderr=PIPE).wait()
    print("\n")
    print("-----------------Dumping Globals Roles finished-------------------")
    print("\n")
    if(p!=0):
        return ""
    return all_roles_dumpfile


def create_global_roles_ontarget(options_dict, all_roles_dumpfile):
    os.environ["PGPASSWORD"] = options_dict.get("target_password")
    command = 'psql -h {0} -U {1} -p {2} -d postgres -b --set ON_ERROR_STOP=off -f {3}'\
    .format(options_dict.get("target_fqdn"),options_dict.get("target_adminuser"),options_dict.get("target_pg_port"),all_roles_dumpfile)
    print("\n")
    print("-----------------Creating Global Roles on Target Server----------------------")
    p = Popen(command,shell=True, stdin=PIPE,stderr=PIPE)
    output, errors = p.communicate()
    # if p.returncode:
    #     print("\n")
    #     print("\n")
    #     print(errors)
    #     return False
    if(errors):
        print(errors)
    else:
        print("-----------------No Errors while Creating Global Roles on Target Server----------------------")
    print("\n")
    print("-----------------Successfully Created Global Roles on Target Server----------------------")
    print("\n")
    return True
    

def run_grants_per_db(options_dict, dumpfile_directory):
    os.environ["PGPASSWORD"] = options_dict.get("target_password")
    for db in options_dict.get('dbs'):
        grant_dump_file_perdb = os.path.join(dumpfile_directory, "{}-roles.sql".format(db))
        command = 'psql -h {0} -U {1} -p {2} -d {3} -b --set ON_ERROR_STOP=off -f {4}'\
        .format(options_dict.get("target_fqdn"),options_dict.get("target_adminuser"),options_dict.get("target_pg_port"),db, grant_dump_file_perdb)
        print(command)
        print("GRANT/REVOKE Statements running for Database: {}".format(db))
        p = Popen(command,shell=True, stdin=PIPE,stderr=PIPE)
        output, errors = p.communicate()
        # if p.returncode or errors:
        #     print("\n")
        #     print("\n")
        #     print(errors)
        #     print("\n")
        #     print("GRANT/REVOKE Statements not run successfully for Database: {}".format(db))
        #     print("\n")
        #     return False
    if(errors):
        print(errors)
    else:
        print("-----------------No Errors while running GRANT Roles on Target Server----------------------")
    return True


def dump_grant_statments_perdb(options_dict, dumpfile_directory):
    os.environ["PGPASSWORD"] = options_dict.get("source_password")
    for db in options_dict.get('dbs'):
        schema_dump_file_perdb = os.path.join(dumpfile_directory, "{}-schema.sql".format(db))
        grant_dump_file_perdb = os.path.join(dumpfile_directory, "{}-roles.sql".format(db))
        command = 'pg_dump -h {0} -U {1} -p {2} -d {3} --schema-only -f {4}'\
        .format(options_dict.get("source_fqdn"),options_dict.get("source_adminuser"),options_dict.get("source_pg_port"),db, schema_dump_file_perdb)
        p = Popen(command,shell=True,stdin=PIPE,stdout=PIPE,stderr=PIPE).wait()
        if p!=0:
            return False
        with open(grant_dump_file_perdb, "w") as outfile:
            subprocess.call(["grep", "-e",  '^\(GRANT\|REVOKE\|ALTER DEFAULT PRIVILEGES\)', schema_dump_file_perdb], stdout=outfile)
        print("\n")
        print("GRANT/REVOKE/ALTER DEFAULT PRIVILEGES statements successfully extracted for database:  {}".format(db))
        print("\n")
    return True

def change_admin_role_grants_perdb(options_dict,dumpfile_directory):
    for db in options_dict.get('dbs'):
        grant_dump_file_perdb = os.path.join(dumpfile_directory, "{}-roles.sql".format(db))
        source_admin_user = options_dict.get("source_adminuser").split("@")[0]
        target_admin_user = options_dict.get("target_adminuser")
        result_code_1 = subprocess.call(["sed", "-i", "-e",  "s/ROLE {0}/ROLE {1}/".format(source_admin_user,target_admin_user), grant_dump_file_perdb])
        result_code_2 = subprocess.call(["sed", "-i", "-e",  "s/TO {0}/TO {1}/".format(source_admin_user,target_admin_user), grant_dump_file_perdb])
        if(any(result_code != 0 for result_code in [result_code_1,result_code_2])):
            print("\n")
            print("Per DB ROLE Dump File not masssaged properly for database {}".format(db))
            print("\n")
            return False
    return True
    
def remove_unwanted_users_from_cluster_dump(options_dict,all_roles_dump_filepath):
    if(os.path.exists(all_roles_dump_filepath)):
        result_code_1 = subprocess.call(["sed", "-i", "-e",  '/ROLE azure_replication/d', all_roles_dump_filepath])
        result_code_2 = subprocess.call(["sed", "-i", "-e",  '/ROLE azure_pg_admin/d', all_roles_dump_filepath])
        result_code_3 = subprocess.call(["sed", "-i", "-e",  '/ROLE azure_superuser/d', all_roles_dump_filepath])
        result_code_4 = subprocess.call(["sed", "-i", "-e",  's/NOSUPERUSER//', all_roles_dump_filepath])
        result_code_5 = subprocess.call(["sed", "-i", "-e",  's/NOBYPASSRLS//', all_roles_dump_filepath])
        result_code_6 = subprocess.call(["sed", "-i", "-e",  '/BY azure_superuser/d', all_roles_dump_filepath])
        result_code_7 = subprocess.call(["sed", "-i", "-e",  "/CREATE ROLE {};/d".format(options_dict.get("source_adminuser").split("@")[0]), all_roles_dump_filepath])
        result_code_8 = subprocess.call(["sed", "-i", "-e",  "/ALTER ROLE {}/d".format(options_dict.get("source_adminuser").split("@")[0]), all_roles_dump_filepath])
        result_code_9 = subprocess.call(["sed", "-i", "-e",  "s/BY {0}/BY {1}/".format(options_dict.get("source_adminuser").split("@")[0],options_dict.get("target_adminuser")), all_roles_dump_filepath])
    else:
        print("\n")
        print("The Cluster Dump File with All the roles has not been created or has been deleted. Please contact Microsoft support")
        print("\n")
    if(any(result_code != 0 for result_code in [result_code_1,result_code_2,result_code_3,result_code_4,result_code_5,result_code_6, result_code_7,result_code_8,result_code_9])):
        print("\n")
        print("The Cluster Role Dump file was not massaged properly. Please contact Microsoft support")
        print("\n")
        return False
    else:
        return True


def check_if_db_exists(options_dict,is_source=True):
    try:
        # connect to the PostgreSQL server
        if is_source:
            conn = psycopg2.connect(database="postgres", user=options_dict.get("source_adminuser"), password=options_dict.get("source_password"), 
            host= options_dict.get("source_fqdn"), port= options_dict.get("source_pg_port"))
        else:
            conn = psycopg2.connect(database="postgres", user=options_dict.get("target_adminuser"), password=options_dict.get("target_password"), 
            host= options_dict.get("target_fqdn"), port= options_dict.get("target_pg_port"))

        # create a cursor
        cur = conn.cursor()
        
        dbs_list = options_dict.get("dbs")
	    # execute a statement
        for db in dbs_list:
            cur.execute("""select exists(SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower('{}'));""".format(db))
            does_db_exist = cur.fetchone()[0]
            if not does_db_exist:
                print("\n")
                print("Database " + db + " does not exist on {} server. Please check the databases passed in to migrate.".format("Source" if is_source else "Target"))
                print("\n")
                return False
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
        raise error
    finally:
        if conn is not None:
            conn.close()
        return True


def check_connectivity(options_dict,is_source=True):
    """ Connect to the PostgreSQL database server """
    conn = None
    result = True
    try:
        # connect to the PostgreSQL server
        if(is_source):
            conn = psycopg2.connect(database="postgres", user=options_dict.get("source_adminuser"), password=options_dict.get("source_password"), 
            host=options_dict.get("source_fqdn"), port= options_dict.get("source_pg_port"))
        else:
            conn = psycopg2.connect(database="postgres", user=options_dict.get("target_adminuser"), password=options_dict.get("target_password"), 
            host= options_dict.get("target_fqdn"), port= options_dict.get("target_pg_port"))

        # create a cursor
        cur = conn.cursor()        
	# execute a statement
        cur.execute('SELECT version();')

        # display the PostgreSQL database server version
        db_version = cur.fetchone()
        print("\n")
        print("{} Server PostgreSQL database version: ".format("Source" if is_source else "Target") + db_version[0])
        print("\n")

	# close the communication with the PostgreSQL
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        result = False
        print(error)
    finally:
        if conn is not None:
            conn.close()
        return result


def process_arguments():
    """
    Process the command line arguments to get the source and target server hostnames, port and admin username/password
    """
    parser = ArgumentParser()

    # Options
    parser.add_argument("-srcfqdn", "--source-FQDN", 
                        dest='source_fqdn', required=True,
                        help="Hostname of the single server PG Server")

    parser.add_argument("-srcuser", "--source-adminusername",
                        dest="source_adminuser", required=True,
                        help="Admin User Name of the Single server PG Server")
    
    parser.add_argument("-srcpgport", "--source-pg-port",
                        dest="source_pg_port", required=True,
                        help="Port on which Single server PG is running")

    sourcepassword = getpass(prompt='Single Server Admin Password: ')

    parser.add_argument("-targetfqdn", "--target-FQDN", required=True,
                        dest='target_fqdn',
                        help="Hostname of the Flexible Server PG Server")

    parser.add_argument("-targetuser", "--target-adminuser",
                        dest="target_adminuser", required=True,
                        help="Admin User Name of the Flexible server PG Server")
    
    parser.add_argument("-targetport", "--target-pg-port",
                        dest="target_pg_port", required=True,
                        help="Port on which Single server PG is running")

    targetpassword = getpass(prompt='Flexible Server Admin Password: ')

    parser.add_argument('--dbs',dest="dbs_to_migrate", nargs='+', required=True, help='Specifies Which Database  you want to migrate the Roles/users for...')
    

   
    args = parser.parse_args()

    options = {}

    options["source_fqdn"] = args.source_fqdn
    options["source_adminuser"] = args.source_adminuser
    options["source_pg_port"] = args.source_pg_port
    options["target_fqdn"] = args.target_fqdn
    options["target_adminuser"] = args.target_adminuser
    options["target_pg_port"] = args.target_pg_port
    options["source_password"] = sourcepassword
    options["target_password"] = targetpassword
    options["dbs"] = args.dbs_to_migrate

    return options



if __name__ == "__main__":
    main()
