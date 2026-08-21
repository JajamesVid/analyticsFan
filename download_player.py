import sys
import subprocess


def normalize(name):
    return name.lower().replace(" ", "_")


if __name__ == "__main__":

    if len(sys.argv) < 3:
        print("Uso: python3 download_player.py 'nombre-jugador-slug' sofascore_id ['Nombre Equipo']")
        sys.exit(1)

    player_name = sys.argv[1]
    sofa_id = sys.argv[2]
    team_name = sys.argv[3] if len(sys.argv) >= 4 else None

    extra = [team_name] if team_name else []

    print(f"\n→ {player_name}")
    subprocess.run(["python3", "sofa_all_stats_download.py", player_name, sofa_id] + extra)
    subprocess.run(["python3", "futFantasy_Pipeline.py", player_name] + extra)
    subprocess.run(["python3", "merge_full_stats.py", player_name] + extra)

    print(f"\n✔ {player_name} completado")
