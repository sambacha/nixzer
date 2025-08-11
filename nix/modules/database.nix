# Flake-compatible NixOS module for database configuration
{ config, pkgs, lib, ... }:

with lib;

let
  cfg = config.services.dozer-database;
in {
  options.services.dozer-database = {
    enable = mkEnableOption "Dozer database configuration";
    
    dbType = mkOption {
      type = types.enum [ "postgresql" "mysql" "mariadb" ];
      default = "postgresql";
      description = "Database type to configure";
    };
    
    dbName = mkOption {
      type = types.str;
      default = "appdb";
      description = "Database name";
    };
    
    dbUser = mkOption {
      type = types.str;
      default = "appuser";
      description = "Database user";
    };
    
    dbPassword = mkOption {
      type = types.str;
      default = "changeme";
      description = "Database password (use secrets management in production)";
    };
    
    enableReplication = mkOption {
      type = types.bool;
      default = false;
      description = "Enable database replication";
    };
    
    backupSchedule = mkOption {
      type = types.str;
      default = "*-*-* 03:00:00";
      description = "Backup schedule in systemd timer format";
    };
  };

  config = mkIf cfg.enable {
    # PostgreSQL configuration
    services.postgresql = mkIf (cfg.dbType == "postgresql") {
      enable = true;
      package = pkgs.postgresql_15;
      
      ensureDatabases = [ cfg.dbName ];
      ensureUsers = [
        {
          name = cfg.dbUser;
          ensureDBOwnership = true;
        }
      ];
      
      authentication = ''
        local all all trust
        host all all 127.0.0.1/32 md5
        host all all ::1/128 md5
      '';
      
      settings = {
        shared_buffers = "256MB";
        max_connections = 100;
        
        # Replication settings
        wal_level = mkIf cfg.enableReplication "replica";
        max_wal_senders = mkIf cfg.enableReplication 3;
        wal_keep_segments = mkIf cfg.enableReplication 64;
      };
      
      initialScript = pkgs.writeText "init-db.sql" ''
        -- Initial database setup
        CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        
        -- Create application schema
        CREATE SCHEMA IF NOT EXISTS app;
        
        -- Grant permissions
        GRANT ALL PRIVILEGES ON DATABASE ${cfg.dbName} TO ${cfg.dbUser};
        GRANT ALL ON SCHEMA app TO ${cfg.dbUser};
        
        -- Set password (in production, use proper secrets management)
        ALTER USER ${cfg.dbUser} WITH PASSWORD '${cfg.dbPassword}';
      '';
    };

    # MySQL/MariaDB configuration
    services.mysql = mkIf (cfg.dbType == "mysql" || cfg.dbType == "mariadb") {
      enable = true;
      package = if cfg.dbType == "mariadb" then pkgs.mariadb else pkgs.mysql80;
      
      ensureDatabases = [ cfg.dbName ];
      ensureUsers = [
        {
          name = cfg.dbUser;
          ensurePermissions = {
            "${cfg.dbName}.*" = "ALL PRIVILEGES";
          };
        }
      ];
      
      settings = {
        mysqld = {
          max_connections = 100;
          innodb_buffer_pool_size = "256M";
          
          # Replication settings
          server_id = mkIf cfg.enableReplication 1;
          log_bin = mkIf cfg.enableReplication "mysql-bin";
          binlog_format = mkIf cfg.enableReplication "ROW";
        };
      };
      
      initialScript = pkgs.writeText "init-mysql.sql" ''
        -- Set user password
        ALTER USER '${cfg.dbUser}'@'localhost' IDENTIFIED BY '${cfg.dbPassword}';
        FLUSH PRIVILEGES;
      '';
    };

    # Database backup timer
    systemd.timers.database-backup = {
      description = "Database backup timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = cfg.backupSchedule;
        Persistent = true;
      };
    };

    systemd.services.database-backup = {
      description = "Database backup service";
      after = [ "${cfg.dbType}.service" ];
      
      serviceConfig = {
        Type = "oneshot";
        User = if cfg.dbType == "postgresql" then "postgres" else "mysql";
        
        ExecStart = pkgs.writeShellScript "db-backup.sh" ''
          #!/usr/bin/env bash
          set -e
          
          BACKUP_DIR="/var/backups/database"
          TIMESTAMP=$(date +%Y%m%d_%H%M%S)
          DB_TYPE="${cfg.dbType}"
          
          mkdir -p "$BACKUP_DIR"
          
          case "$DB_TYPE" in
            postgresql)
              ${pkgs.postgresql}/bin/pg_dump ${cfg.dbName} | \
                ${pkgs.gzip}/bin/gzip > "$BACKUP_DIR/${cfg.dbName}_$TIMESTAMP.sql.gz"
              ;;
            mysql|mariadb)
              ${pkgs.mysql}/bin/mysqldump ${cfg.dbName} | \
                ${pkgs.gzip}/bin/gzip > "$BACKUP_DIR/${cfg.dbName}_$TIMESTAMP.sql.gz"
              ;;
          esac
          
          # Keep only last 7 days of backups
          ${pkgs.findutils}/bin/find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
          
          echo "Database backup completed: $BACKUP_DIR/${cfg.dbName}_$TIMESTAMP.sql.gz"
        '';
      };
    };

    # Monitoring and health checks
    systemd.services.database-health-check = {
      description = "Database health check";
      after = [ "${cfg.dbType}.service" ];
      
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "db-health.sh" ''
          #!/usr/bin/env bash
          set -e
          
          case "${cfg.dbType}" in
            postgresql)
              ${pkgs.postgresql}/bin/psql -U ${cfg.dbUser} -d ${cfg.dbName} -c "SELECT 1" > /dev/null
              ;;
            mysql|mariadb)
              ${pkgs.mysql}/bin/mysql -u ${cfg.dbUser} -p${cfg.dbPassword} ${cfg.dbName} -e "SELECT 1" > /dev/null
              ;;
          esac
          
          echo "Database health check passed"
        '';
      };
    };

    systemd.timers.database-health-check = {
      description = "Database health check timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*:0/5"; # Every 5 minutes
        Persistent = true;
      };
    };

    # Firewall rules for database
    networking.firewall = {
      allowedTCPPorts = 
        if cfg.dbType == "postgresql" then [ 5432 ]
        else [ 3306 ];
    };
  };
}