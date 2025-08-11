{ config, pkgs, lib, ... }:
{
  # Generated from Ansible playbook using Dozer approach
  # Syscall analysis identified equivalent NixOS modules

  environment.systemPackages = with pkgs; [
    docker
    docker-compose
  ];

  users.users = {
    dockeruser = {
      isNormalUser = true;
      createHome = true;
      extraGroups = "docker";
      shell = pkgs.bash;
      description = "Docker Service User";
    };
  };

  systemd.services = {
    docker = {
      enable = true;
      wantedBy = ["multi-user.target"];
    };
  };

  systemd.timers = {
    container-health-check = {
      description = "Container health check";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "daily";
      };
      serviceConfig = {
        ExecStart = "/usr/local/bin/check-containers.sh >> /var/log/container-check.log 2>&1";
      };
    };
  };

}