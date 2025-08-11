{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    nginx
  ];

  systemd.services = {
    nginx = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  environment.etc = {
    "nginx/sites-available/mysite" = {
      text = ''
        server {
            listen 80;
            server_name mysite.local;
            root /var/www/mysite;
            index index.html;
            
            location / {
                try_files $uri $uri/ =404;
            }
        }
      '';
      mode = "0644";
    };
    "nginx/sites-enabled/mysite" = {
      source = "/etc/nginx/sites-available/mysite";
    };
  };

}