FROM python:3.14-slim

# UID/GID do usuário do host: o container precisa ser o mesmo usuário
# para conseguir abrir os sockets do Wayland/X11 e ler as HQs montadas
ARG UID=1000
ARG GID=1000

# Bibliotecas de sistema usadas pelo Qt (Wayland e X11) e pelo libarchive (CBR/CBZ)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libarchive13t64 \
        libgl1 libegl1 libglib2.0-0t64 libdbus-1-3 libfontconfig1 fonts-dejavu-core \
        libxkbcommon0 libxkbcommon-x11-0 \
        libwayland-client0 libwayland-cursor0 libwayland-egl1 \
        libx11-xcb1 libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xfixes0 libxcb-xinerama0 libxcb-xkb1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "$GID" app \
    && useradd --uid "$UID" --gid "$GID" --create-home app \
    && mkdir -p /home/app/.config /comics \
    && chown app:app /home/app/.config

WORKDIR /opt/comic-library

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

USER app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    QT_QPA_PLATFORM="wayland;xcb" \
    QT_X11_NO_MITSHM=1 \
    COMIC_LIBRARY_FOLDER=/comics

CMD ["python", "-m", "app.main"]
