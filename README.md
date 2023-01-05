# Migrate Azure Database for Postgresql Single Server to Flexible Server using Flexible Migration Service (FMS)

 FMS is a managed migration service provided by Microsoft to migrate databases from Azure database for PostgreSQL Single server to Azure Database for PostgreSQL Flexible server.

 In order to get started with the migration tooling, please use the following sign up form - https://forms.office.com/r/pvA7vy455P

 Please reach out to us at AskAzureDBforPGS2F@microsoft.com for any kind of support needed on migrations from Single server to Flexible server. 

## Introduction

The Single to Flexible server migration tool is designed to move databases from Azure Database for PostgreSQL Single server to Flexible server. We launched the preview version of the tool also known as the **Migration (Preview)** feature in Flexible server, back in August 2022 for customers to try out migrations. The preview version used an infrastructure based on Azure Database Migration Service (DMS). We have aggregated feedback from customers and have come up with an improved version of the migration tool which will use a new infrastructure to perform migrations in a more easy, robust and resilient way. This document will help you understand the functioning of the new version of the tool along with its limitations and the pre-requisites that need to be taken care of before using the tool.    

Currently, the new version of the tool only supports **Offline** mode of migration. Offline mode presents a simple and hassle-free way to migrate your databases but might incur downtime to your server depending on the size of the databases and the way in which data is distributed across tables in your database.

## How does it work?

The new version of the migration tool is a hosted solution where we spin up a purpose-built docker container in the target Flexible server VM and drive the incoming migrations. This docker container will be spun up on-demand when a migration is initiated from a single server and will be decommissioned as soon as the migration is completed. The migration container will use a new binary called [**pgcopydb**](https://github.com/dimitri/pgcopydb) which provides a fast and efficient way of copying databases from one server to another. Though pgcopydb uses the traditional pg_dump and pg_restore for schema migration, it implements its own data migration mechanism which involves multi-process streaming parts from source to target. Also, pgcopydb bypasses pg_restore way of index building and drives that internally in a way that all indexes can be built concurrently. So, the data migration process is much quicker with pgcopydb. Following is the process diagram of the new version of the migration tool.

![Process diagram](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/ProcessDiagram.png)

The following table shows the approximate time for performing offline migrations for databases of various sizes using the new version of the tool. Note that the migration was performed on the **General-Purpose Flexible server with Standard_D4s_v3 SKU (4VCore), 4TB Storage and 6400 IOPs.**

| Database size | Approximate time taken (HH:MM:SS) |
|:---------------|:-------------|
| 1 GB | 00:00:01 |
| 5 GB | 00:00:03 |
| 10 GB | 00:00:08 |
| 50 GB | 01:45:00 |
| 100 GB | 06:00:00 |
| 500 GB | 08:00:00 |
| 1,000 GB | 09:30:00 |

The below table has data on the time taken to perform offline migration with **General-Purpose flexible server with Standard_D8s_v3 SKU (8VCore), 4TB storage and 7500 IOPs.**

| Database size | Approximate time taken (HH:MM:SS) |
|:---------------|:-------------|
| 1 GB | 00:00:30 |
| 5 GB | 00:02:00 |
| 10 GB | 00:04:00 |
| 50 GB | 01:15:00 |
| 100 GB | 05:00:00 |
| 500 GB | 06:00:00 |
| 1,000 GB | 07:30:00 |

Please note that these numbers are the average time taken to complete offline migration for a database with a given size with multiple different schemas and with varying data distribution.

From the above data, it is very clear that with a higher compute on Flexible server, the migration will complete faster. It is a good practice to create a flexible server with a higher SKU and complete the migrations from single server in a quick way. Post successful migrations, you can tune the SKU of your flexible server to meet the application requirements.

## Limitations

- You can have only one active migration to your flexible server.
- Only a max of 8 databases can be included in one migration attempt from single to flexible server. If you have more than 8 databases, you must wait for the first migration to be completed before initiating another migration for the rest of the databases. Support for migration of more than 8 databases will be introduced in a later version of the tool.
- Only offline mode is supported as of now. Online mode will be introduced later in a later version of migration tool.
- The source and target server must be in the same Azure region. Cross region migrations will not work in this version of the migration tool. 
- Collation mismatches between single and flexible server are not handled by the tool. If there is a collation used in single server that does not exist in flexible server, the migration will fail.
- The migration tool does not migrate users and roles. You should consider creating users and roles in your flexible server after the completion of data migration.

## Best practices for Offline Migration

- Offline migrations will require a downtime of your application. So, plan for a time slot when the application can take a maintenance window.
- Before initiating the migration, stop all the applications that connect to your single server.
- Create a flexible server with a General-Purpose or Memory Optimized compute tier. Avoid Burstable SKUs since it might take longer time to complete the migration due to non-availability of dedicated CPUs.
- Pick a higher SKU size for flexible server. Go for a minimum of 8VCore or higher to complete the offline migration quickly.
- Do not include HA or geo redundancy option while creating flexible server. You can always enable it with zero downtime once the migration from single server is completed.
- Once the migration is completed, please verify the data on your flexible server and make sure it is an exact copy of the single server.
- Post verification, enable HA/ backup options as needed on your flexible server.
- Change the SKU of the flexible server to match the application needs. Note that this change will need a database server restart.
- Migrate users and roles from single to flexible servers. This can be done in a manual way by creating users on flexible servers and providing them with suitable privileges or by using this [**Python script**](https://microsoftapc-my.sharepoint.com/:w:/g/personal/chajain_microsoft_com/Ea8cRd0rGX5FtDPaJPBL6roBVinu0qWLDXotpCsI5cF-4g?wdOrigin=TEAMS-ELECTRON.p2p.p2p&wdExp=TEAMS-CONTROL&wdhostclicktime=1670907831526&web=1&wdLOR=cD6324225-CC1F-4A46-80EB-78998A059782) which automates the process.
- Make changes to your application to point the connection strings to flexible server.
- Monitor the database performance closely to see if performance tuning is required. 

## How can customers consume it?

The new version of the migration tool can be consumed from Azure Portal. Once you share your subscription details, we will enable the new version of the migration tool on your subscription. 

### Pre-requisites

Here is the list of pre-requisites to get started with the migration tool. 

 - [Create a flexible server with higher SKU for migration purposes.](https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/quickstart-create-server-portal)
 - [Enable all extensions used in single server on flexible server.](https://learn.microsoft.com/en-us/azure/postgresql/migrate/concepts-single-to-flexible#allow-list-required-extensions)
 - Enable network connectivity from target flexible server to single server.
     - If both single and flexible servers are public access, there is no action needed from your end to establish connectivity. The migration tool automatically allow-lists the IP of flexible server in single server.
     - If single server is public access and flexible server is inside a VNet, please allow connections from the VNet of flexible server to your single server by adding a [VNet rule or service end point](https://learn.microsoft.com/en-us/azure/postgresql/single-server/concepts-data-access-and-security-vnet).
     - If the single server is behind a private end point and flexible server is public access, there is no way to establish connectivity between the servers. The migrations will fail, and this scenario is not supported by the new version of the migration tool.
     - If the single server is behind a private end point and flexible server is inside a VNet, ensure the VNets associated with private end point and flexible server are connected. This will involve VNet peering if VNets of source and target are different. If both are in the same VNet, make sure there is no network security group (NSG) rule that is blocking the connectivity between the flexible server and single server.

### Portal Experience

Once the pre-requisite steps are taken care of, you can perform the following steps to create an offline migration using the new version of the tool.

- Go to your Azure Database for PostgreSQL Flexible Server. Scroll down to **Migration (preview)** option and select it.

![Portal Pic1](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic1.png)

- Select the **Migrate from Single Server button** to start a migration from Single Server to Flexible Server. 

![Portal Pic2](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic2.png)

- This opens a wizard with a series of tabs. First is the **setup** tab which prompts for a migration name. Please ensure that all extensions used in single server are enabled on the flexible server.

![Portal Pic3](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic3.png)

Enter a valid migration name and select the **Next** button.

- The next is the **Source** tab

![Portal Pic4](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic4.png)

Pick the subscription and resource group of your single server and provide the password for the admin user of your single server. Pick up to a maximum of 8 databases for the migration and click on the **Next** button.

- The next is the **Target** tab

![Portal Pic5](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic5.png)

Please provide the password for the admin user of flexible server and the rest of the details are already filled out. Click on the **Next** button.

- The final tab is the **Review and Create**.

![Portal Pic6](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic6.png)

Review the information and click on the **Create** button.

### Monitoring migrations

After you hit the Create button, a notification appears in a few seconds to say that the migration was successfully created. You should automatically be redirected to the **Migration (Preview)** page of Flexible Server. It should have a new entry for the recently created migration.

![Portal Pic7](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic7.png)

You can also select the migration name in the grid to see the details of that migration.

![Portal Pic8](https://github.com/shriram-muthukrishnan/pg-singletoflex/blob/main/images/PortalPic8.png)

Use the refresh button to get the latest status of the migration. Over time, the migration will succeed or fail with appropriate errors.

### Support

Please reach out to us at AskAzureDBforPGS2F@microsoft.com for any kind of support needed on migrations from single server to flexible server. 