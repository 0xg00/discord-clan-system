import discord
from discord.ext import commands
import sqlite3
import asyncio

# ID del administrador
ADMIN_ID = 879376076579688508



# Conectar a la base de datos
conn = sqlite3.connect('clans.db')
c = conn.cursor()

# Crear tablas si no existen
c.execute('''CREATE TABLE IF NOT EXISTS clans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                owner_id INTEGER NOT NULL,
                messages INTEGER DEFAULT 0
            )''')

c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER NOT NULL,
                clan_id INTEGER,
                FOREIGN KEY (clan_id) REFERENCES clans(id)
            )''')
conn.commit()

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="..", intents=intents)

@bot.event
async def on_ready():
    print(f'Bot {bot.user} is ready.')

@bot.event
async def on_message(message):
    if not message.author.bot:
        c.execute("SELECT clan_id FROM users WHERE user_id = ?", (message.author.id,))
        user_clan = c.fetchone()

        if user_clan:
            clan_id = user_clan[0]
            c.execute("UPDATE clans SET messages = messages + 1 WHERE id = ?", (clan_id,))
            conn.commit()

    await bot.process_commands(message)

@bot.command()
async def join(ctx, clan_id: int):
    c.execute("SELECT name FROM clans WHERE id = ?", (clan_id,))
    clan = c.fetchone()

    # Verificar si el usuario ya está en un clan
    c.execute("SELECT clan_id FROM users WHERE user_id = ?", (ctx.author.id,))
    user_clan = c.fetchone()

    if user_clan:
        embed = discord.Embed(
            title="Error",
            description="Ya estás en un clan. Debes abandonarlo antes de unirte a otro.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    if clan:
        c.execute("INSERT OR REPLACE INTO users (user_id, clan_id) VALUES (?, ?)", (ctx.author.id, clan_id))
        conn.commit()
        embed = discord.Embed(
            title="Unión al Clan Exitosa",
            description=f'Te has unido al clan **"{clan[0]}"**.',
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="El clan no existe.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@join.error
async def join_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan. Uso: `..join <IDdelClan>`')

@bot.command()
async def borrar(ctx, clan_id: int):
    # Verificar si el autor del mensaje es el propietario del clan
    c.execute("SELECT owner_id FROM clans WHERE id = ?", (clan_id,))
    clan_owner = c.fetchone()
    if not clan_owner or ctx.author.id != clan_owner[0]:
        await ctx.send("No tienes permiso para borrar este clan.")
        return

    # Eliminar el clan y a sus miembros
    c.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
    c.execute("DELETE FROM users WHERE clan_id = ?", (clan_id,))
    conn.commit()
    await ctx.send(f"El clan con ID {clan_id} ha sido borrado exitosamente.")

@borrar.error
async def borrar_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan. Uso: `..borrar <IDdelClan>`')

@bot.command()
async def clan(ctx):
    c.execute("SELECT clans.name, clans.owner_id, COUNT(users.user_id) as members, clans.messages FROM clans LEFT JOIN users ON clans.id = users.clan_id WHERE clans.id IN (SELECT clan_id FROM users WHERE user_id = ?) GROUP BY clans.id", (ctx.author.id,))
    clan_info = c.fetchone()

    if clan_info:
        name, owner_id, members, messages = clan_info
        try:
            owner = await bot.fetch_user(owner_id)  # Obtener el usuario correctamente
            owner_mention = owner.mention  # Mencionar al propietario
        except discord.NotFound:
            owner_mention = "Desconocido"
            owner_name = "Desconocido"
        embed = discord.Embed(
            title=f"Información del Clan {name}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Propietario",
            value=f"{owner_mention}",
            inline=False
        )
        embed.add_field(
            name="Miembros",
            value=members,
            inline=False
        )
        embed.add_field(
            name="Mensajes",
            value=messages,
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="No estás en ningún clan.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command()
async def create(ctx, *, clan_name: str):
    # Verificar si el usuario ya está en un clan
    c.execute("SELECT clan_id FROM users WHERE user_id = ?", (ctx.author.id,))
    user_clan = c.fetchone()

    if user_clan:
        embed = discord.Embed(
            title="Error",
            description="Ya estás en un clan. Debes abandonarlo antes de crear otro.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        try:
            # Insertar el clan en la base de datos
            c.execute("INSERT INTO clans (name, owner_id) VALUES (?, ?)", (clan_name, ctx.author.id))
            conn.commit()
            # Obtener el ID del clan recién creado
            c.execute("SELECT id FROM clans WHERE name = ?", (clan_name,))
            clan_id = c.fetchone()[0]
            # Unir automáticamente al creador al clan
            c.execute("INSERT OR REPLACE INTO users (user_id, clan_id) VALUES (?, ?)", (ctx.author.id, clan_id))
            conn.commit()

            # Crear un mensaje de confirmación más bonito
            embed = discord.Embed(
                title="Clan Creado",
                description=f"¡Felicidades! Has creado el clan **{clan_name}** con éxito.",
                color=discord.Color.green()
            )
            embed.add_field(name="ID del clan:", value=clan_id, inline=False)
            embed.add_field(name="Propietario:", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"¡Únete al clan '{clan_name}' ahora mismo!")
            await ctx.send(embed=embed)
        except sqlite3.IntegrityError:
            embed = discord.Embed(
                title="Error",
                description="El nombre del clan ya existe. Por favor elige otro.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f'No se pudo crear el clan. Intenta de nuevo. Error: {e}',
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)


@create.error
async def create_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un nombre para el clan. Uso: `..create <nombre_del_clan>`')

@bot.command()
async def delete(ctx, clan_id: int):
    # Verificar si el autor del mensaje es el administrador
    if ctx.author.id != ADMIN_ID:
        embed = discord.Embed(
            title="Error",
            description="No tienes permiso para utilizar este comando.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Obtener el nombre del clan
    c.execute("SELECT name FROM clans WHERE id = ?", (clan_id,))
    clan_name = c.fetchone()

    if clan_name:
        clan_name = clan_name[0]
        # Eliminar el clan y a sus miembros
        c.execute("DELETE FROM clans WHERE id = ?", (clan_id,))
        c.execute("DELETE FROM users WHERE clan_id = ?", (clan_id,))
        conn.commit()
        embed = discord.Embed(
            title="Clan Eliminado",
            description=f'El clan "{clan_name}" y todos sus miembros han sido eliminados.',
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="El clan no existe.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@delete.error
async def delete_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan. Uso: `..delete <IDdelClan>`')


@bot.command()
async def transfer(ctx, clan_id: int, new_owner: discord.Member):
    # Verificar si el autor del mensaje es el administrador
    if ctx.author.id != ADMIN_ID:
        embed = discord.Embed(
            title="Error",
            description="No tienes permiso para utilizar este comando.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Verificar si el clan existe
    c.execute("SELECT owner_id FROM clans WHERE id = ?", (clan_id,))
    owner_id = c.fetchone()

    if owner_id:
        owner_id = owner_id[0]
        # Transferir la propiedad del clan al nuevo propietario
        c.execute("UPDATE clans SET owner_id = ? WHERE id = ?", (new_owner.id, clan_id))

        # Eliminar al usuario anterior del clan
        c.execute("DELETE FROM users WHERE user_id = ? AND clan_id = ?", (ctx.author.id, clan_id))

        # Agregar al nuevo propietario al clan si no estaba en ningún clan
        c.execute("SELECT clan_id FROM users WHERE user_id = ?", (new_owner.id,))
        new_owner_clan = c.fetchone()
        if not new_owner_clan:
            c.execute("INSERT INTO users (user_id, clan_id) VALUES (?, ?)", (new_owner.id, clan_id))

        conn.commit()

        embed = discord.Embed(
            title="Transferencia Exitosa",
            description=f'El clan con ID {clan_id} ahora es propiedad de {new_owner.mention}.',
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="El clan no existe.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@transfer.error
async def transfer_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan y menciona al nuevo propietario. Uso: `..transfer <IDdelClan> <@nuevoPropietario>`')

@bot.command()
async def obtain(ctx, clan_id: int):
    # Verificar si el autor del mensaje es el administrador
    if ctx.author.id != ADMIN_ID:
        embed = discord.Embed(
            title="Error",
            description="No tienes permiso para utilizar este comando.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # Verificar si el clan existe
    c.execute("SELECT owner_id FROM clans WHERE id = ?", (clan_id,))
    owner_id = c.fetchone()

    if owner_id:
        owner_id = owner_id[0]
        # Asignar la propiedad del clan al administrador
        c.execute("UPDATE clans SET owner_id = ? WHERE id = ?", (ADMIN_ID, clan_id))
        conn.commit()
        embed = discord.Embed(
            title="Propiedad Obtenida",
            description=f'Ahora tienes la propiedad del clan con ID {clan_id}.',
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="El clan no existe.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@obtain.error
async def obtain_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan. Uso: `..obtain <IDdelClan>`')

@bot.command()
async def leave(ctx):
    # Verificar si el usuario está en un clan
    c.execute("SELECT clan_id FROM users WHERE user_id = ?", (ctx.author.id,))
    user_clan = c.fetchone()

    if user_clan:
        c.execute("SELECT owner_id FROM clans WHERE id = ?", (user_clan[0],))
        owner_id = c.fetchone()[0]
        if ctx.author.id == owner_id:
            embed = discord.Embed(
                title="Advertencia",
                description="Al abandonar el clan como propietario, se eliminará el clan y todos sus miembros. ¿Estás seguro de que deseas continuar?",
                color=discord.Color.red()
            )
            msg = await ctx.send(embed=embed)
            await msg.add_reaction('✅')  # Reacción de confirmación
            await msg.add_reaction('❌')  # Reacción de cancelación

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ['✅', '❌']

            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await ctx.send("Se agotó el tiempo para la respuesta.")
                return

            if str(reaction.emoji) == '✅':
                # Eliminar el clan y a sus miembros
                c.execute("DELETE FROM clans WHERE id = ?", (user_clan[0],))
                c.execute("DELETE FROM users WHERE clan_id = ?", (user_clan[0],))
                conn.commit()
                embed = discord.Embed(
                    title="Clan Eliminado",
                    description="El clan y todos sus miembros han sido eliminados.",
                    color=discord.Color.green()
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Operación Cancelada",
                    description="La operación ha sido cancelada.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
        else:
            # Eliminar al usuario del clan
            c.execute("DELETE FROM users WHERE user_id = ?", (ctx.author.id,))
            conn.commit()
            embed = discord.Embed(
                title="Abandono Exitoso",
                description="Has abandonado el clan.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="No estás en ningún clan.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command()
async def top(ctx):
    c.execute("SELECT clans.id, clans.name, clans.owner_id, COUNT(users.user_id) as members, clans.messages FROM clans LEFT JOIN users ON clans.id = users.clan_id GROUP BY clans.id ORDER BY members DESC, clans.messages DESC")
    clans = c.fetchall()

    if clans:
        embed = discord.Embed(
            title="Top Clanes",
            color=discord.Color.gold()
        )

        for i, clan in enumerate(clans):
            clan_id, name, owner_id, members, messages = clan
            rank = i + 1
            try:
                owner = await bot.fetch_user(owner_id)  # Cambio para obtener el usuario correctamente
                owner_name = owner.display_name if owner else "Desconocido"
                owner_mention = owner.mention if owner else "Desconocido"
            except discord.NotFound:
                owner_name = "Desconocido"
                owner_mention = "Desconocido"
            embed.add_field(
                name=f"{rank}. {name} (ID: {clan_id})",
                value=f"**Propietario:** {owner_mention}\n**Miembros:** {members}\n**Mensajes:** {messages}",
                inline=False
            )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="No hay clanes registrados.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command()
async def members(ctx, clan_id: int):
    c.execute("SELECT users.user_id, users.clan_id FROM users INNER JOIN clans ON users.clan_id = clans.id WHERE clans.id = ?", (clan_id,))
    clan_members = c.fetchall()

    if clan_members:
        member_list = []
        for member in clan_members:
            try:
                member_user = await bot.fetch_user(member[0])
                member_mention = member_user.mention  # Mencionar al usuario
                member_list.append(member_mention)
            except discord.NotFound:
                pass

        if member_list:
            embed = discord.Embed(
                title=f"Miembros del Clan con ID: {clan_id}",
                description="\n".join(member_list),
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Error",
                description="No se pudo encontrar información sobre los miembros del clan.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Error",
            description="El clan no tiene miembros.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@members.error
async def members_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send('Por favor proporciona un ID de clan. Uso: `..members <IDdelClan>`')
    elif isinstance(error, commands.BadArgument):
        await ctx.send('El ID del clan debe ser un número entero.')
    elif isinstance(error, commands.CommandInvokeError):
        await ctx.send('Ocurrió un error al procesar el comando. Asegúrate de que el ID del clan sea válido.')


# Deshabilitar el comando help
bot.remove_command('help')

@bot.command()
async def help(ctx):
    embed = discord.Embed(
        title="Comandos de Clanes",
        description="Una lista de comandos disponibles para la gestión de clanes.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="..create <nombre>",
        value="Crea un nuevo clan con el nombre especificado.",
        inline=False
    )
    embed.add_field(
        name="..join <ID>",
        value="Únete a un clan existente usando su ID.",
        inline=False
    )
    embed.add_field(
        name="..leave",
        value="Abandona el clan al que estás unido actualmente.",
        inline=False
    )
    embed.add_field(
        name="..transfer <ID> <@miembro>",
        value="Transfiere la propiedad de un clan a otro miembro (solo el administrador puede usar este comando).",
        inline=False
    )
    embed.add_field(
        name="..clan",
        value="Muestra información sobre el clan al que estás unido actualmente.",
        inline=False
    )
    embed.add_field(
        name="..top",
        value="Muestra los mejores clanes según la cantidad de miembros y mensajes.",   
        inline=False
    )
    embed.add_field(
        name="..members <ID>",
        value="Muestra una lista de miembros para un clan específico.",
        inline=False
    )
    await ctx.send(embed=embed)

@bot.command()
async def shutdown(ctx):
    if ctx.author.id == ADMIN_ID:
        await ctx.send("Apagando el bot...")
        await bot.close()
    else:
        await ctx.send("Solo el administrador puede apagar el bot.")

bot.run('')