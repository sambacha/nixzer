{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    postgresql
  ];

  users.users = {
    dbadmin = {
      isNormalUser = true;
      createHome = true;
      extraGroups = "postgres";
      shell = pkgs.bash;
      description = "Database Administrator";
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
        local   all   postgres   peer
        local   all   all        md5
        host    all   all        0.0.0.0/0   md5
      '';
      mode = "0640";
      user = "postgres";
      group = "postgres";
    };
  };

  systemd.timers = {
    database-backup = {
      description = "Database backup";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "daily";
      };
      serviceConfig = {
        ExecStart = "/usr/local/bin/backup-db.sh";
        User = "postgres";
      };
    };
  };

}