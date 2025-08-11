{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    postgresql
    python3-psycopg2
  ];

  users.users = {
    dbadmin = {
      isNormalUser = true;
      createHome = true;
      extraGroups = ["postgres", "sudo"];
      shell = pkgs.bash;
      description = "Database Administrator";
    };
    appuser = {
      isNormalUser = true;
      createHome = false;
      shell = pkgs.false;
      description = "Application Database User";
    };
  };

  systemd.services = {
    postgresql = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  environment.etc = {
    "postgresql/13/main/pg_hba.conf" = {
      text = ''
        # Database administrative login by Unix domain socket
        local   all             postgres                                peer
        
        # TYPE  DATABASE        USER            ADDRESS                 METHOD
        local   all             all                                     md5
        host    all             all             127.0.0.1/32            md5
        host    all             all             ::1/128                 md5
        host    all             all             10.0.0.0/8              md5
      '';
      mode = "0640";
      user = "postgres";
      group = "postgres";
    };
  };

  systemd.timers = {
    postgresql-backup = {
      description = "PostgreSQL backup";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "daily";
      };
      serviceConfig = {
        ExecStart = "/usr/local/bin/backup-postgres.sh";
        User = "postgres";
      };
    };
  };

}