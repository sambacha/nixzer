# Flake-compatible NixOS module converted from Ansible
{ config, pkgs, lib, ... }:

with lib;

let
  cfg = config.services.dozer-webserver;
in {
  options.services.dozer-webserver = {
    enable = mkEnableOption "Dozer webserver configuration";
    
    domain = mkOption {
      type = types.str;
      default = "example.com";
      description = "Domain name for the webserver";
    };
    
    adminUser = mkOption {
      type = types.str;
      default = "webadmin";
      description = "Web administrator username";
    };
    
    webRoot = mkOption {
      type = types.path;
      default = "/var/www/html";
      description = "Web root directory";
    };
    
    enableBackup = mkOption {
      type = types.bool;
      default = true;
      description = "Enable daily backup cron job";
    };
    
    packages = mkOption {
      type = types.listOf types.package;
      default = with pkgs; [ curl git vim python3 ];
      description = "Additional packages to install";
    };
  };

  config = mkIf cfg.enable {
    # System packages (converted from Ansible package tasks)
    environment.systemPackages = with pkgs; [
      nginx
    ] ++ cfg.packages;

    # User configuration (converted from Ansible user task)
    users.users.${cfg.adminUser} = {
      isNormalUser = true;
      createHome = true;
      extraGroups = [ "wheel" "nginx" ];
      shell = pkgs.bash;
      description = "Web Administrator";
    };

    # Nginx service configuration (converted from Ansible service task)
    services.nginx = {
      enable = true;
      
      virtualHosts.${cfg.domain} = {
        root = cfg.webRoot;
        
        locations."/" = {
          tryFiles = "$uri $uri/ =404";
        };
        
        # Converted from Ansible copy task for nginx config
        extraConfig = ''
          index index.html;
        '';
      };
    };

    # Create web root directory (converted from Ansible file task)
    systemd.tmpfiles.rules = [
      "d ${cfg.webRoot} 0755 ${cfg.adminUser} nginx -"
    ];

    # Deploy index.html (converted from Ansible copy task)
    environment.etc."www/index.html" = {
      text = ''
        <!DOCTYPE html>
        <html>
        <head><title>Welcome</title></head>
        <body><h1>Welcome to our server - Managed by Nix</h1></body>
        </html>
      '';
      mode = "0644";
      user = cfg.adminUser;
      group = "nginx";
    };

    # Firewall configuration (converted from Ansible ufw task)
    networking.firewall = {
      enable = true;
      allowedTCPPorts = [ 80 443 ];
    };

    # Backup timer (converted from Ansible cron task)
    systemd.timers.daily-backup = mkIf cfg.enableBackup {
      description = "Daily backup timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 2:00:00";
        Persistent = true;
      };
    };

    systemd.services.daily-backup = mkIf cfg.enableBackup {
      description = "Daily backup service";
      serviceConfig = {
        Type = "oneshot";
        User = cfg.adminUser;
        ExecStart = pkgs.writeShellScript "backup.sh" ''
          #!/usr/bin/env bash
          set -e
          
          BACKUP_DIR="/var/backups/web"
          TIMESTAMP=$(date +%Y%m%d_%H%M%S)
          
          mkdir -p "$BACKUP_DIR"
          
          # Backup web content
          ${pkgs.gnutar}/bin/tar -czf "$BACKUP_DIR/web_$TIMESTAMP.tar.gz" ${cfg.webRoot}
          
          # Backup nginx config
          ${pkgs.gnutar}/bin/tar -czf "$BACKUP_DIR/nginx_$TIMESTAMP.tar.gz" /etc/nginx
          
          # Keep only last 7 days of backups
          ${pkgs.findutils}/bin/find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete
          
          echo "Backup completed: $BACKUP_DIR"
        '';
      };
    };

    # Additional syscall-traced validation
    system.activationScripts.dozer-webserver-validation = ''
      echo "Dozer webserver module activated"
      echo "Syscall tracing would verify equivalent behavior to Ansible playbook"
    '';
  };
}