import asyncio
import websockets
import json
import random
import time
import html
import os

# Fichier de données centralisé
data_file = "player_data.json"

# Chargement des coins des joueurs à partir d'un fichier JSON
def load_data():
    """Charge les données des joueurs à partir d'un fichier JSON centralisé."""
    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            data = json.load(f)
            return data.get("coins", {})
    return {}

# Sauvegarde des données des joueurs dans un fichier JSON
def save_data(player_coins):
    """Sauvegarde les données des joueurs dans un fichier JSON centralisé."""
    data = {
        "coins": player_coins
    }
    with open(data_file, "w") as f:
        json.dump(data, f)
    print(f"Données sauvegardées : {data}")

# Initialisation des variables de jeu
player_last_played = {}
last_message_time = 0  # Dernière fois qu'un message a été envoyé
connected_users = {}  # Dictionnaire pour stocker les utilisateurs connectés

# Règles du jeu, formatées pour envoi ligne par ligne
rules_text = [
    "--Bienvenue dans le jeu casino de Loult.family !** 🎉",
    "",
    "--Règles et Commandes :**",
    "1. --Objectif** : Pariez vos coins pour tenter de doubler vos gains, mais attention, vous risquez aussi de les perdre !",
    "   Si votre solde tombe à zéro, vous regagnez automatiquement 1 coin toutes les minutes.",
    "",
    "2. --Commandes de jeu** :",
    "   - --!mrle <montant> <multiplicateur>** : Pariez un montant de coins. Si vous gagnez, vous doublez (ou plus) votre mise selon le multiplicateur.",
    "     En cas de défaite, vous perdez votre mise.",
    "   - --!bank** : Consultez votre solde actuel de coins.",
    "   - --!give <montant> <nom> <adjectif>** : Transférez un nombre spécifique de coins à un autre joueur.",
    "",
    "3. --Transactions** :",
    "   - Achetez 1000 coins pour 0,10 centime ou vendez 1,000 coins pour 0,1 centime.",
    "",
    "--Bon jeu et bonne chance !**"
]

async def coin_regeneration(player_coins):
    """Fonction pour régénérer les coins des joueurs toutes les minutes."""
    while True:
        for userid, coins in player_coins.items():
            if userid in player_last_played and coins < 15:
                player_coins[userid] += 1
                player_coins[userid] = round(player_coins[userid], 2)
                print(f"Régénération : {userid} gagne 1 coin. Nouveau solde : {player_coins[userid]}")
        await asyncio.sleep(60)

async def send_message(websocket, message_data):
    """Envoie un message avec un délai minimum entre les messages."""
    global last_message_time
    current_time = time.time()
    time_since_last_message = current_time - last_message_time

    if time_since_last_message < 0.4:
        await asyncio.sleep(0.4 - time_since_last_message)

    message_json = json.dumps(message_data)
    await websocket.send(message_json)

    last_message_time = time.time()

async def connect_to_loult_family(player_coins):
    uri = "wss://loult.family/socket/casino"
    headers = {
        'Cookie': 'id=371eec5730312c873f95ab6838f5bb3bn',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36',
        'Origin': 'https://loult.family/casino'
    }

    try:
        async with websockets.connect(uri, extra_headers=headers) as websocket:
            message = json.dumps({"type": "greeting", "content": "Bonjour, Loult.family!"})
            await websocket.send(message)
            print(f"Envoyé: {message}")

            while True:
                try:
                    response = await websocket.recv()
                    if isinstance(response, str):
                        try:
                            data = json.loads(response)

                            if data.get("type") == "userlist":
                                for user in data["users"]:
                                    userid = user["userid"]
                                    name = user["params"]["name"]
                                    adjective = user["params"]["adjective"]
                                    connected_users[userid] = (name, adjective)
                                    if userid not in player_coins:
                                        player_coins[userid] = 10  # Initialiser avec 10 coins si nouveau joueur
                                        print(f"Initialisation de {userid} avec 10 coins.")
                                    print(f"Utilisateur ajouté : {userid} - {name} ({adjective})")

                            elif data.get("type") == "msg":
                                msg_content = html.unescape(data.get("msg")).lower().strip()
                                userid = data.get("userid")

                                if userid not in player_coins:
                                    player_coins[userid] = 10
                                    print(f"Initialisation de {userid} avec 10 coins.")

                                if msg_content.startswith("!mrle"):
                                    parts = msg_content.split()
                                    if len(parts) > 1 and (str(parts[1]).isdigit() or parts[1] == 'all-in'):
                                        if parts[1] == 'all-in':
                                            bet_amount = int(player_coins[userid])
                                            is_all_in = True
                                        else:
                                            bet_amount = int(parts[1])
                                            is_all_in = False

                                        multiplier = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

                                        if player_coins[userid] < bet_amount:
                                            response_message = {"type": "msg", "msg": f"Vous n'avez pas assez de coins pour miser {bet_amount}. Solde actuel : {player_coins[userid]} coins."}
                                        elif bet_amount == 0:
                                            response_message = {"type": "msg", "msg": "Erreur : vous ne pouvez pas parier 0 coins."}
                                        else:
                                            player_last_played[userid] = time.time()
                                            result = "gagné" if random.random() < (1 / (2 ** multiplier)) else "perdu"

                                            if result == "gagné":
                                                winnings = bet_amount * multiplier
                                                player_coins[userid] += winnings
                                                result_msg = (
                                                    "Bravo tu as porter tes balls te voilà riche"
                                                    if is_all_in
                                                    else f"✅✅ gagné ! 🎉 Vous gagnez {winnings} coins."
                                                )
                                            else:
                                                player_coins[userid] -= bet_amount
                                                result_msg = (
                                                    "Perdu retour chez les prolo"
                                                    if is_all_in
                                                    else f"❌❌ perdu {bet_amount} coin(s)."
                                                )

                                            player_coins[userid] = round(player_coins[userid], 2)
                                            response_message = {"type": "me", "msg": f"{result_msg} Votre solde actuel est de {player_coins[userid]} coins."}

                                        await send_message(websocket, response_message)
                                        print(f"Envoyé: {response_message}")
                                        save_data(player_coins)

                                elif msg_content == "!rules":
                                    for line in rules_text:
                                        response_message = {"type": "msg", "msg": line}
                                        await send_message(websocket, response_message)

                                elif msg_content.startswith("!bank"):
                                    response_message = {
                                        "type": "msg",
                                        "msg": f"Votre solde de coins est de {player_coins[userid]} coins."
                                    }
                                    await send_message(websocket, response_message)

                                elif msg_content.startswith("!give"):
                                    parts = msg_content.split()
                                    if len(parts) >= 4 and str(parts[1]).isdigit():
                                        amount = int(parts[1])
                                        target_name = parts[2]
                                        target_adjective = ' '.join(parts[3:])

                                        target_userid = None
                                        for uid, (name, adjective) in connected_users.items():
                                            if name.lower() == target_name.lower() and adjective.lower() == target_adjective.lower():
                                                target_userid = uid
                                                break

                                        if target_userid and player_coins[userid] >= amount:
                                            player_coins[userid] -= amount
                                            player_coins[target_userid] += amount
                                            response_message = {"type": "msg", "msg": f"Vous avez donné {amount} coins à {target_name.capitalize()} !"}

                                            # Sauvegarder après une transaction réussie
                                            save_data(player_coins)
                                        else:
                                            response_message = {"type": "msg", "msg": "Erreur : montant invalide ou joueur non trouvé."}
                                        await send_message(websocket, response_message)

                            # Autres types de messages peuvent être traités ici

                        except Exception as e:
                            print(f"Erreur lors du traitement de la réponse : {e}")

                except Exception as recv_error:
                    print(f"Erreur lors de la réception du message : {recv_error}")

    except Exception as e:
        print(f"Erreur lors de la connexion : {e}")

async def main():
    player_coins = load_data()  # Charger les coins ici
    asyncio.create_task(coin_regeneration(player_coins))  # Démarrer la régénération des coins
    await connect_to_loult_family(player_coins)  # Lancer la connexion au WebSocket

# Lancer le programme
if __name__ == "__main__":
    asyncio.run(main())
