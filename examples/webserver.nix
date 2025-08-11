{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    curl
    git
    nginx
    python3
    vim
  ];

  users.users = {
    webadmin = {
      isNormalUser = true;
      createHome = true;
      extraGroups = ["wheel", "www-data"];
      shell = pkgs.bash;
      description = "Web Administrator";
    };
  };

  systemd.services = {
    nginx = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  environment.etc = {
    "nginx/sites-available/default" = {
      text = ''
        server {
            listen 80;
            server_name example.com;
            root /var/www/html;
            index index.html;
            
            location / {
                try_files $uri $uri/ =404;
            }
        }
      '';
      mode = "0644";
    };
  };

  networking.firewall = {
    enable = true;
    allowedTCPPorts = ["80"];
  };

  systemd.timers = {
    daily-backup = {
      description = "Daily backup";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "*-*-* 2:00:00";
      };
      serviceConfig = {
        ExecStart = "/usr/local/bin/backup.sh";
        User = "webadmin";
      };
    };
  };

}