FROM python:3.11

WORKDIR /app

COPY csa_aci_fixed/ /csa_aci_fixed/

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e /csa_aci_fixed

COPY backend/ .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]