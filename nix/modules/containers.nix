# Flake-compatible NixOS module for container orchestration
# Converts Docker Compose configurations to Nix containers
{ config, pkgs, lib, ... }:

with lib;

let
  cfg = config.services.dozer-containers;
  
  # Helper to create OCI container configurations
  mkContainer = name: containerCfg: {
    image = containerCfg.image;
    ports = containerCfg.ports or [];
    environment = containerCfg.environment or {};
    volumes = containerCfg.volumes or [];
    dependsOn = containerCfg.dependsOn or [];
    cmd = containerCfg.command or [];
    extraOptions = containerCfg.extraOptions or [];
  };
  
in {
  options.services.dozer-containers = {
    enable = mkEnableOption "Dozer container orchestration";
    
    backend = mkOption {
      type = types.enum [ "docker" "podman" "nixos-container" ];
      default = "podman";
      description = "Container backend to use";
    };
    
    network = mkOption {
      type = types.str;
      default = "dozer-network";
      description = "Container network name";
    };
    
    containers = mkOption {
      type = types.attrsOf (types.submodule {
        options = {
          image = mkOption {
            type = types.str;
            description = "Container image";
          };
          
          ports = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Port mappings (host:container)";
          };
          
          environment = mkOption {
            type = types.attrsOf types.str;
            default = {};
            description = "Environment variables";
          };
          
          volumes = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Volume mounts";
          };
          
          dependsOn = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Container dependencies";
          };
          
          command = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Override container command";
          };
          
          extraOptions = mkOption {
            type = types.listOf types.str;
            default = [];
            description = "Extra container runtime options";
          };
        };
      });
      default = {};
      description = "Container definitions";
    };
    
    # Example application stack configuration
    exampleStack = {
      enable = mkEnableOption "Example application stack";
      
      nginxConfig = mkOption {
        type = types.lines;
        default = ''
          events {
            worker_connections 1024;
          }
          
          http {
            upstream api {
              server api:8000;
            }
            
            server {
              listen 80;
              server_name localhost;
              
              location / {
                root /usr/share/nginx/html;
                index index.html;
              }
              
              location /api/ {
                proxy_pass http://api/;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
              }
            }
          }
        '';
        description = "Nginx configuration";
      };
    };
  };

  config = mkIf cfg.enable {
    # Install container runtime
    environment.systemPackages = with pkgs; [
      (if cfg.backend == "docker" then docker
       else if cfg.backend == "podman" then podman
       else nixos-container)
      docker-compose  # For compatibility
      skopeo  # For image management
      dive    # For image inspection
    ];

    # Enable container backend
    virtualisation = {
      docker.enable = cfg.backend == "docker";
      podman = mkIf (cfg.backend == "podman") {
        enable = true;
        dockerCompat = true;  # Docker compatibility
        defaultNetwork.settings.dns_enabled = true;
      };
      oci-containers = {
        backend = cfg.backend;
        containers = mapAttrs mkContainer cfg.containers;
      };
    };

    # Create container network
    systemd.services.container-network-setup = {
      description = "Setup container network";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];
      
      serviceConfig = {
        Type = "oneshot";
        RemainAfterExit = true;
        ExecStart = pkgs.writeShellScript "setup-network.sh" ''
          #!/usr/bin/env bash
          set -e
          
          BACKEND="${cfg.backend}"
          NETWORK="${cfg.network}"
          
          case "$BACKEND" in
            docker)
              ${pkgs.docker}/bin/docker network create $NETWORK 2>/dev/null || true
              ;;
            podman)
              ${pkgs.podman}/bin/podman network create $NETWORK 2>/dev/null || true
              ;;
          esac
          
          echo "Container network $NETWORK ready"
        '';
      };
    };

    # Example stack deployment
    systemd.services = mkIf cfg.exampleStack.enable {
      # Web container
      container-web = {
        description = "Web container (nginx)";
        after = [ "container-network-setup.service" ];
        wantedBy = [ "multi-user.target" ];
        
        serviceConfig = {
          Type = "simple";
          Restart = "unless-stopped";
          ExecStartPre = pkgs.writeShellScript "prepare-web.sh" ''
            # Prepare nginx config
            mkdir -p /opt/containers/nginx
            cat > /opt/containers/nginx/nginx.conf << 'EOF'
            ${cfg.exampleStack.nginxConfig}
            EOF
          '';
          
          ExecStart = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker run --rm --name web " +
              "--network ${cfg.network} " +
              "-p 80:80 -p 443:443 " +
              "-v /opt/containers/nginx/nginx.conf:/etc/nginx/nginx.conf:ro " +
              "nginx:alpine"
            else
              "${pkgs.podman}/bin/podman run --rm --name web " +
              "--network ${cfg.network} " +
              "-p 80:80 -p 443:443 " +
              "-v /opt/containers/nginx/nginx.conf:/etc/nginx/nginx.conf:ro " +
              "docker.io/nginx:alpine";
          
          ExecStop = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker stop web"
            else
              "${pkgs.podman}/bin/podman stop web";
        };
      };
      
      # API container
      container-api = {
        description = "API container (Python)";
        after = [ "container-network-setup.service" "container-db.service" ];
        wantedBy = [ "multi-user.target" ];
        
        serviceConfig = {
          Type = "simple";
          Restart = "unless-stopped";
          
          ExecStart = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker run --rm --name api " +
              "--network ${cfg.network} " +
              "-p 8000:8000 " +
              "-e DATABASE_URL=postgresql://api:secret@db:5432/apidb " +
              "-e REDIS_URL=redis://cache:6379/0 " +
              "python:3.11-alpine python -m http.server 8000"
            else
              "${pkgs.podman}/bin/podman run --rm --name api " +
              "--network ${cfg.network} " +
              "-p 8000:8000 " +
              "-e DATABASE_URL=postgresql://api:secret@db:5432/apidb " +
              "-e REDIS_URL=redis://cache:6379/0 " +
              "docker.io/python:3.11-alpine python -m http.server 8000";
          
          ExecStop = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker stop api"
            else
              "${pkgs.podman}/bin/podman stop api";
        };
      };
      
      # Database container
      container-db = {
        description = "Database container (PostgreSQL)";
        after = [ "container-network-setup.service" ];
        wantedBy = [ "multi-user.target" ];
        
        serviceConfig = {
          Type = "simple";
          Restart = "unless-stopped";
          
          ExecStart = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker run --rm --name db " +
              "--network ${cfg.network} " +
              "-e POSTGRES_DB=apidb " +
              "-e POSTGRES_USER=api " +
              "-e POSTGRES_PASSWORD=secret " +
              "-v postgres_data:/var/lib/postgresql/data " +
              "postgres:15-alpine"
            else
              "${pkgs.podman}/bin/podman run --rm --name db " +
              "--network ${cfg.network} " +
              "-e POSTGRES_DB=apidb " +
              "-e POSTGRES_USER=api " +
              "-e POSTGRES_PASSWORD=secret " +
              "-v postgres_data:/var/lib/postgresql/data " +
              "docker.io/postgres:15-alpine";
          
          ExecStop = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker stop db"
            else
              "${pkgs.podman}/bin/podman stop db";
        };
      };
      
      # Cache container
      container-cache = {
        description = "Cache container (Redis)";
        after = [ "container-network-setup.service" ];
        wantedBy = [ "multi-user.target" ];
        
        serviceConfig = {
          Type = "simple";
          Restart = "unless-stopped";
          
          ExecStart = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker run --rm --name cache " +
              "--network ${cfg.network} " +
              "-v redis_data:/data " +
              "redis:7-alpine"
            else
              "${pkgs.podman}/bin/podman run --rm --name cache " +
              "--network ${cfg.network} " +
              "-v redis_data:/data " +
              "docker.io/redis:7-alpine";
          
          ExecStop = 
            if cfg.backend == "docker" then
              "${pkgs.docker}/bin/docker stop cache"
            else
              "${pkgs.podman}/bin/podman stop cache";
        };
      };
    };

    # Container health monitoring
    systemd.services.container-health-monitor = {
      description = "Container health monitoring";
      after = [ "multi-user.target" ];
      
      serviceConfig = {
        Type = "oneshot";
        ExecStart = pkgs.writeShellScript "check-containers.sh" ''
          #!/usr/bin/env bash
          set -e
          
          BACKEND="${cfg.backend}"
          
          echo "Checking container health..."
          
          case "$BACKEND" in
            docker)
              ${pkgs.docker}/bin/docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
              ;;
            podman)
              ${pkgs.podman}/bin/podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
              ;;
          esac
          
          # Check if containers need restart
          for container in web api db cache; do
            if ! ${pkgs.docker}/bin/docker ps | grep -q "$container"; then
              echo "Container $container not running, restarting..."
              systemctl restart "container-$container.service" || true
            fi
          done
        '';
      };
    };

    systemd.timers.container-health-monitor = {
      description = "Container health monitoring timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*:0/5"; # Every 5 minutes
        Persistent = true;
      };
    };

    # Firewall configuration
    networking.firewall = {
      allowedTCPPorts = [ 80 443 8000 ];
    };
  };
}