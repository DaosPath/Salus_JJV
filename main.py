import sys
from datetime import datetime
import json
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QLineEdit, QMessageBox, QComboBox, QHeaderView, QLabel, QSpinBox,
    QFileDialog
)
from PyQt6.QtGui import QAction, QFont, QIcon, QPainter
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
from sqlalchemy import create_engine, Column, Integer, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import IntegrityError

# Configuración del engine con pool ampliado
DATABASE_URL = "sqlite:///database.db"
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Producto(Base):
    __tablename__ = "productos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(255), nullable=False)
    descripcion = Column(String)
    precio_compra = Column(Numeric(10, 2), nullable=False)
    precio_venta = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False)
    categoria = Column(String(100))
    fecha_vencimiento = Column(Date)
    codigo_barras = Column(String(50), unique=True)

class InventarioEntry(Base):
    __tablename__ = "inventario"
    id = Column(Integer, primary_key=True)
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer, nullable=False)
    fecha_ingreso = Column(DateTime, default=lambda: datetime.now(), onupdate=lambda: datetime.now())

class Venta(Base):
    __tablename__ = "ventas"
    id = Column(Integer, primary_key=True)
    fecha = Column(DateTime, default=lambda: datetime.now())
    total = Column(Numeric(10, 2), nullable=False)
    caja_id = Column(Integer, ForeignKey("caja.id"), nullable=True)

class DetalleVenta(Base):
    __tablename__ = "detalle_ventas"
    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"))
    producto_id = Column(Integer, ForeignKey("productos.id"))
    cantidad = Column(Integer, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

class Caja(Base):
    __tablename__ = "caja"
    id = Column(Integer, primary_key=True)
    fecha_apertura = Column(DateTime, default=lambda: datetime.now(), nullable=False)
    fecha_cierre = Column(DateTime, nullable=True)
    monto_apertura = Column(Numeric(10, 2), nullable=False)
    monto_cierre = Column(Numeric(10, 2), nullable=True)
    total_ventas = Column(Numeric(10, 2), nullable=True)

class VentaCancelada(Base):
    __tablename__ = "ventas_canceladas"
    id = Column(Integer, primary_key=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"))
    fecha_cancelacion = Column(DateTime, default=lambda: datetime.now())
    motivo = Column(String(255))

Base.metadata.create_all(engine)

def generar_reporte_excel(caja):
    session = SessionLocal()
    resumen_data = {
        "Caja ID": caja.id,
        "Fecha Apertura": caja.fecha_apertura.strftime("%Y-%m-%d %H:%M:%S"),
        "Monto Apertura": float(caja.monto_apertura),
        "Fecha Cierre": caja.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S") if caja.fecha_cierre else "Caja abierta",
        "Monto Cierre": float(caja.monto_cierre) if caja.monto_cierre is not None else 0.0,
        "Total Ventas": float(caja.total_ventas) if caja.total_ventas else 0.0,
    }
    saldo_final = float(caja.monto_apertura) + (float(caja.total_ventas) if caja.total_ventas else 0.0)
    resumen_data["Saldo Final"] = saldo_final

    df_resumen = pd.DataFrame([resumen_data])
    
    query = session.query(Venta, DetalleVenta, Producto)\
        .join(DetalleVenta, Venta.id == DetalleVenta.venta_id)\
        .join(Producto, Producto.id == DetalleVenta.producto_id)\
        .filter(Venta.caja_id == caja.id).all()
    detalle_list = []
    for venta, detalle, producto in query:
        detalle_list.append({
            "Venta ID": venta.id,
            "Fecha Venta": venta.fecha.strftime("%Y-%m-%d %H:%M:%S"),
            "Producto": producto.nombre,
            "Cantidad": detalle.cantidad,
            "Precio Venta": float(producto.precio_venta),
            "Subtotal": float(detalle.subtotal)
        })
    df_detalle = pd.DataFrame(detalle_list)
    if not df_detalle.empty:
        df_productos = df_detalle.groupby("Producto", as_index=False)\
            .agg({"Cantidad": "sum", "Subtotal": "sum"})\
            .rename(columns={"Cantidad": "Cantidad Total", "Subtotal": "Total Ventas"})
    else:
        df_productos = pd.DataFrame(columns=["Producto", "Cantidad Total", "Total Ventas"])
    
    filename, _ = QFileDialog.getSaveFileName(None, "Guardar reporte Excel", "", "Excel Files (*.xlsx)")
    if filename:
        try:
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                df_resumen.to_excel(writer, sheet_name="Resumen Caja", index=False)
                df_detalle.to_excel(writer, sheet_name="Detalle Ventas", index=False)
                df_productos.to_excel(writer, sheet_name="Productos Vendidos", index=False)
            QMessageBox.information(None, "Reporte Excel", "Reporte generado exitosamente.")
        except Exception as e:
            QMessageBox.warning(None, "Reporte Excel", f"Error al exportar: {str(e)}")
    session.close()

def generar_reporte_excel_venta(venta):
    session = SessionLocal()
    venta_info = {
        "Venta ID": venta.id,
        "Fecha": venta.fecha.strftime("%Y-%m-%d %H:%M:%S"),
        "Total": float(venta.total)
    }
    df_venta = pd.DataFrame([venta_info])
    query = session.query(DetalleVenta, Producto)\
        .join(Producto, Producto.id == DetalleVenta.producto_id)\
        .filter(DetalleVenta.venta_id == venta.id).all()
    detalle_list = []
    for detalle, producto in query:
        detalle_list.append({
            "Producto": producto.nombre,
            "Cantidad": detalle.cantidad,
            "Precio Venta": float(producto.precio_venta),
            "Subtotal": float(detalle.subtotal)
        })
    df_detalle = pd.DataFrame(detalle_list)
    if not df_detalle.empty:
        df_productos = df_detalle.groupby("Producto", as_index=False)\
            .agg({"Cantidad": "sum", "Subtotal": "sum"})\
            .rename(columns={"Cantidad": "Cantidad Total", "Subtotal": "Total Ventas"})
    else:
        df_productos = pd.DataFrame(columns=["Producto", "Cantidad Total", "Total Ventas"])
    filename, _ = QFileDialog.getSaveFileName(None, "Guardar reporte Excel de Venta", "", "Excel Files (*.xlsx)")
    if filename:
        try:
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                df_venta.to_excel(writer, sheet_name="Venta", index=False)
                df_detalle.to_excel(writer, sheet_name="Detalle Venta", index=False)
                df_productos.to_excel(writer, sheet_name="Productos Vendidos", index=False)
            QMessageBox.information(None, "Reporte Excel", "Reporte de venta generado exitosamente.")
        except Exception as e:
            QMessageBox.warning(None, "Reporte Excel", f"Error al exportar: {str(e)}")
    session.close()

def exportar_base_datos_json():
    session = SessionLocal()
    data = {}
    models = [Producto, InventarioEntry, Venta, DetalleVenta, Caja, VentaCancelada]
    for model in models:
        table_name = model.__tablename__
        items = session.query(model).all()
        data[table_name] = [{col.name: getattr(item, col.name) for col in model.__table__.columns} for item in items]
    filename, _ = QFileDialog.getSaveFileName(None, "Exportar Base de Datos", "", "JSON Files (*.json)")
    if filename:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, default=str)
            QMessageBox.information(None, "Exportar Base de Datos", "Base de datos exportada exitosamente.")
        except Exception as e:
            QMessageBox.warning(None, "Exportar Base de Datos", f"Error al exportar: {str(e)}")
    session.close()

class ReportePreviewDialog(QDialog):
    def __init__(self, caja, parent=None):
        super().__init__(parent)
        self.caja = caja
        self.setWindowTitle(f"Previsualización Reporte - Caja ID: {caja.id}")
        self.resize(700, 500)
        layout = QVBoxLayout(self)
        self.tablaDetalle = QTableWidget()
        self.tablaDetalle.setColumnCount(6)
        self.tablaDetalle.setHorizontalHeaderLabels(["Venta ID", "Fecha Venta", "Producto", "Cantidad", "Precio Venta", "Subtotal"])
        header = self.tablaDetalle.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tablaDetalle)
        self.cargar_detalle()
        btnExportar = QPushButton("Exportar a Excel")
        btnExportar.clicked.connect(self.generar_reporte)
        layout.addWidget(btnExportar)
    
    def cargar_detalle(self):
        session = SessionLocal()
        query = session.query(Venta, DetalleVenta, Producto)\
            .join(DetalleVenta, Venta.id == DetalleVenta.venta_id)\
            .join(Producto, Producto.id == DetalleVenta.producto_id)\
            .filter(Venta.caja_id == self.caja.id).all()
        self.tablaDetalle.setRowCount(len(query))
        for i, (venta, detalle, producto) in enumerate(query):
            self.tablaDetalle.setItem(i, 0, QTableWidgetItem(str(venta.id)))
            self.tablaDetalle.setItem(i, 1, QTableWidgetItem(venta.fecha.strftime("%Y-%m-%d %H:%M:%S")))
            self.tablaDetalle.setItem(i, 2, QTableWidgetItem(producto.nombre))
            self.tablaDetalle.setItem(i, 3, QTableWidgetItem(str(detalle.cantidad)))
            self.tablaDetalle.setItem(i, 4, QTableWidgetItem(str(producto.precio_venta)))
            self.tablaDetalle.setItem(i, 5, QTableWidgetItem(str(detalle.subtotal)))
        session.close()
    
    def generar_reporte(self):
        generar_reporte_excel(self.caja)

class ProductoDialog(QDialog):
    def __init__(self, parent=None, producto=None):
        super().__init__(parent)
        self.producto = producto
        self.setWindowTitle("Agregar Producto" if producto is None else "Editar Producto")
        self.layout = QFormLayout(self)
        self.inputNombre = QLineEdit()
        self.inputDescripcion = QLineEdit()
        self.inputPrecioCompra = QLineEdit()
        self.inputPrecioVenta = QLineEdit()
        self.inputStock = QLineEdit()
        self.inputCategoria = QLineEdit()
        self.inputFechaVenc = QLineEdit()
        self.inputCodigoBarras = QLineEdit()
        if producto:
            self.inputNombre.setText(producto.nombre)
            self.inputDescripcion.setText(producto.descripcion or "")
            self.inputPrecioCompra.setText(str(producto.precio_compra))
            self.inputPrecioVenta.setText(str(producto.precio_venta))
            self.inputStock.setText(str(producto.stock))
            self.inputCategoria.setText(producto.categoria or "")
            self.inputFechaVenc.setText(str(producto.fecha_vencimiento or ""))
            self.inputCodigoBarras.setText(producto.codigo_barras or "")
        self.layout.addRow("Nombre", self.inputNombre)
        self.layout.addRow("Descripción", self.inputDescripcion)
        self.layout.addRow("Precio Compra", self.inputPrecioCompra)
        self.layout.addRow("Precio Venta", self.inputPrecioVenta)
        self.layout.addRow("Stock", self.inputStock)
        self.layout.addRow("Categoría", self.inputCategoria)
        self.layout.addRow("Fecha Venc. (YYYY-MM-DD)", self.inputFechaVenc)
        self.layout.addRow("Código Barras", self.inputCodigoBarras)
        btnLayout = QHBoxLayout()
        btnGuardar = QPushButton("Guardar")
        btnCancelar = QPushButton("Cancelar")
        btnGuardar.clicked.connect(self.accept)
        btnCancelar.clicked.connect(self.reject)
        btnLayout.addWidget(btnGuardar)
        btnLayout.addWidget(btnCancelar)
        self.layout.addRow(btnLayout)

    def get_data(self):
        try:
            precio_compra = float(self.inputPrecioCompra.text()) if self.inputPrecioCompra.text() else 0.0
            precio_venta = float(self.inputPrecioVenta.text()) if self.inputPrecioVenta.text() else 0.0
        except ValueError:
            QMessageBox.warning(self, "Error", "Los precios deben ser números")
            return None
        data = {
            "nombre": self.inputNombre.text().strip(),
            "descripcion": self.inputDescripcion.text().strip(),
            "precio_compra": precio_compra,
            "precio_venta": precio_venta,
            "stock": int(self.inputStock.text()) if self.inputStock.text() else 0,
            "categoria": self.inputCategoria.text().strip(),
            "codigo_barras": self.inputCodigoBarras.text().strip() or None
        }
        fecha_text = self.inputFechaVenc.text().strip()
        if fecha_text:
            try:
                data["fecha_vencimiento"] = datetime.strptime(fecha_text, "%Y-%m-%d").date()
            except ValueError:
                QMessageBox.warning(self, "Error", "La fecha debe tener el formato YYYY-MM-DD")
                return None
        else:
            data["fecha_vencimiento"] = None
        return data

class VentanaProductos(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setLayout(QVBoxLayout())
        # Buscador de productos para vender
        self.busquedaLineEdit = QLineEdit()
        self.busquedaLineEdit.setPlaceholderText("Buscar producto para vender...")
        self.busquedaLineEdit.textChanged.connect(self.cargar_productos)
        self.layout().addWidget(self.busquedaLineEdit)
        # Tabla de productos (9 columnas)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(9)
        self.tabla.setHorizontalHeaderLabels(["ID", "Nombre", "Descripción", "Precio Compra", "Precio Venta", "Inventario", "Precio Absoluto", "Categoría", "Código Barras"])
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout().addWidget(self.tabla)
        btnLayout = QHBoxLayout()
        btnAgregar = QPushButton("Agregar")
        btnEditar = QPushButton("Editar")
        btnEliminar = QPushButton("Eliminar")
        btnLayout.addWidget(btnAgregar)
        btnLayout.addWidget(btnEditar)
        btnLayout.addWidget(btnEliminar)
        self.layout().addLayout(btnLayout)
        btnAgregar.clicked.connect(self.agregar_producto)
        btnEditar.clicked.connect(self.editar_producto)
        btnEliminar.clicked.connect(self.eliminar_producto)
        self.cargar_productos()

    def cargar_productos(self):
        busqueda = self.busquedaLineEdit.text().strip().lower()
        productos = self.sesion.query(Producto).all()
        if busqueda:
            productos = [p for p in productos if busqueda in p.nombre.lower()]
        self.tabla.setRowCount(len(productos))
        for i, p in enumerate(productos):
            self.tabla.setItem(i, 0, QTableWidgetItem(str(p.id)))
            self.tabla.setItem(i, 1, QTableWidgetItem(p.nombre))
            self.tabla.setItem(i, 2, QTableWidgetItem(p.descripcion or ""))
            self.tabla.setItem(i, 3, QTableWidgetItem(str(p.precio_compra)))
            self.tabla.setItem(i, 4, QTableWidgetItem(str(p.precio_venta)))
            self.tabla.setItem(i, 5, QTableWidgetItem(str(p.stock)))
            precio_absoluto = float(p.precio_compra) * p.stock
            self.tabla.setItem(i, 6, QTableWidgetItem(f"{precio_absoluto:.2f}"))
            self.tabla.setItem(i, 7, QTableWidgetItem(p.categoria or ""))
            self.tabla.setItem(i, 8, QTableWidgetItem(p.codigo_barras or ""))

    def agregar_producto(self):
        dlg = ProductoDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data is None:
                return
            nuevo = Producto(**data)
            self.sesion.add(nuevo)
            try:
                self.sesion.commit()
            except IntegrityError:
                self.sesion.rollback()
                QMessageBox.warning(self, "Error", "Ya existe un producto con ese código de barras.")
            self.cargar_productos()

    def editar_producto(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona un producto")
            return
        producto_id = int(self.tabla.item(fila, 0).text())
        producto = self.sesion.query(Producto).filter_by(id=producto_id).first()
        dlg = ProductoDialog(self, producto)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data is None:
                return
            for clave, valor in data.items():
                setattr(producto, clave, valor)
            try:
                self.sesion.commit()
            except IntegrityError:
                self.sesion.rollback()
                QMessageBox.warning(self, "Error", "No se pudo actualizar el producto. Verifica el código de barras.")
            self.cargar_productos()

    def eliminar_producto(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona un producto")
            return
        producto_id = int(self.tabla.item(fila, 0).text())
        producto = self.sesion.query(Producto).filter_by(id=producto_id).first()
        if QMessageBox.question(self, "Eliminar", f"¿Eliminar {producto.nombre}?") == QMessageBox.StandardButton.Yes:
            try:
                self.sesion.delete(producto)
                self.sesion.commit()
            except IntegrityError:
                self.sesion.rollback()
                reply = QMessageBox.question(
                    self,
                    "Error",
                    "No se puede eliminar el producto. Existen conexiones asociadas.\n\n¿Desea realizar una Eliminación Extrema (se eliminarán todas las referencias asociadas)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.destruir_producto(producto)
            self.cargar_productos()

    def destruir_producto(self, producto):
        try:
            inventario_entries = self.sesion.query(InventarioEntry).filter_by(producto_id=producto.id).all()
            for entry in inventario_entries:
                self.sesion.delete(entry)
            detalles = self.sesion.query(DetalleVenta).filter_by(producto_id=producto.id).all()
            for detalle in detalles:
                self.sesion.delete(detalle)
            self.sesion.delete(producto)
            self.sesion.commit()
            QMessageBox.information(self, "Eliminación Extrema", f"Producto {producto.nombre} y todas sus referencias han sido eliminadas.")
        except Exception as e:
            self.sesion.rollback()
            QMessageBox.warning(self, "Error", f"Error al eliminar el producto de forma extrema: {str(e)}")

class InventarioDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Agregar Stock")
        self.layout = QFormLayout(self)
        self.comboProducto = QComboBox()
        self.sesion = SessionLocal()
        for prod in self.sesion.query(Producto).all():
            self.comboProducto.addItem(f"{prod.nombre} (ID: {prod.id})", prod.id)
        self.inputCantidad = QLineEdit()
        self.layout.addRow("Producto", self.comboProducto)
        self.layout.addRow("Cantidad a agregar", self.inputCantidad)
        btnLayout = QHBoxLayout()
        btnGuardar = QPushButton("Guardar")
        btnCancelar = QPushButton("Cancelar")
        btnGuardar.clicked.connect(self.accept)
        btnCancelar.clicked.connect(self.reject)
        btnLayout.addWidget(btnGuardar)
        btnLayout.addWidget(btnCancelar)
        self.layout.addRow(btnLayout)

    def get_data(self):
        try:
            cantidad = int(self.inputCantidad.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "La cantidad debe ser un número entero")
            return None
        return {"producto_id": self.comboProducto.currentData(), "cantidad": cantidad}

class InventarioEditDialog(QDialog):
    def __init__(self, parent=None, cantidad_actual=0):
        super().__init__(parent)
        self.setWindowTitle("Modificar Entrada de Stock")
        self.layout = QFormLayout(self)
        self.inputCantidad = QLineEdit()
        self.inputCantidad.setText(str(cantidad_actual))
        self.layout.addRow("Nueva cantidad", self.inputCantidad)
        btnLayout = QHBoxLayout()
        btnGuardar = QPushButton("Guardar")
        btnCancelar = QPushButton("Cancelar")
        btnGuardar.clicked.connect(self.accept)
        btnCancelar.clicked.connect(self.reject)
        btnLayout.addWidget(btnGuardar)
        btnLayout.addWidget(btnCancelar)
        self.layout.addRow(btnLayout)

    def get_nueva_cantidad(self):
        try:
            return int(self.inputCantidad.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "La cantidad debe ser un número entero")
            return None

class VentanaInventario(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setLayout(QVBoxLayout())
        self.busquedaLineEdit = QLineEdit()
        self.busquedaLineEdit.setPlaceholderText("Buscar en inventario por producto...")
        self.busquedaLineEdit.textChanged.connect(self.cargar_inventario)
        self.layout().addWidget(self.busquedaLineEdit)
        self.tabla = QTableWidget()
        self.tabla.setColumnCount(5)
        self.tabla.setHorizontalHeaderLabels(["ID", "Producto", "Cantidad", "Fecha Ingreso", "Precio Absoluto"])
        header = self.tabla.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout().addWidget(self.tabla)
        btnLayout = QHBoxLayout()
        btnAgregar = QPushButton("Agregar Stock")
        btnModificar = QPushButton("Modificar Entrada")
        btnEliminar = QPushButton("Eliminar Entrada")
        btnLayout.addWidget(btnAgregar)
        btnLayout.addWidget(btnModificar)
        btnLayout.addWidget(btnEliminar)
        self.layout().addLayout(btnLayout)
        btnAgregar.clicked.connect(self.agregar_entrada)
        btnModificar.clicked.connect(self.modificar_entrada)
        btnEliminar.clicked.connect(self.eliminar_entrada)
        self.cargar_inventario()

    def cargar_inventario(self):
        busqueda = self.busquedaLineEdit.text().strip().lower()
        entradas = self.sesion.query(InventarioEntry).all()
        if busqueda:
            entradas = [e for e in entradas if busqueda in (self.sesion.query(Producto).filter_by(id=e.producto_id).first().nombre.lower() if self.sesion.query(Producto).filter_by(id=e.producto_id).first() else "")]
        self.tabla.setRowCount(len(entradas))
        for i, entry in enumerate(entradas):
            self.tabla.setItem(i, 0, QTableWidgetItem(str(entry.id)))
            prod = self.sesion.query(Producto).filter_by(id=entry.producto_id).first()
            producto_nombre = prod.nombre if prod else "Desconocido"
            self.tabla.setItem(i, 1, QTableWidgetItem(producto_nombre))
            self.tabla.setItem(i, 2, QTableWidgetItem(str(entry.cantidad)))
            self.tabla.setItem(i, 3, QTableWidgetItem(entry.fecha_ingreso.strftime("%Y-%m-%d %H:%M:%S")))
            if prod:
                precio_absoluto = float(prod.precio_compra) * entry.cantidad
            else:
                precio_absoluto = 0
            self.tabla.setItem(i, 4, QTableWidgetItem(f"{precio_absoluto:.2f}"))

    def agregar_entrada(self):
        dlg = InventarioDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data is None:
                return
            prod = self.sesion.query(Producto).filter_by(id=data["producto_id"]).first()
            if prod:
                prod.stock += data["cantidad"]
            nueva = InventarioEntry(producto_id=data["producto_id"], cantidad=data["cantidad"], fecha_ingreso=datetime.now())
            self.sesion.add(nueva)
            self.sesion.commit()
            self.cargar_inventario()

    def modificar_entrada(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona una entrada")
            return
        entrada_id = int(self.tabla.item(fila, 0).text())
        entrada = self.sesion.query(InventarioEntry).filter_by(id=entrada_id).first()
        if not entrada:
            QMessageBox.warning(self, "Error", "Entrada no encontrada")
            return
        dlg = InventarioEditDialog(self, cantidad_actual=entrada.cantidad)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nueva = dlg.get_nueva_cantidad()
            if nueva is None:
                return
            diferencia = nueva - entrada.cantidad
            entrada.cantidad = nueva
            prod = self.sesion.query(Producto).filter_by(id=entrada.producto_id).first()
            if prod:
                prod.stock += diferencia
            self.sesion.commit()
            self.cargar_inventario()

    def eliminar_entrada(self):
        fila = self.tabla.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona una entrada")
            return
        entrada_id = int(self.tabla.item(fila, 0).text())
        entrada = self.sesion.query(InventarioEntry).filter_by(id=entrada_id).first()
        if not entrada:
            QMessageBox.warning(self, "Error", "Entrada no encontrada")
            return
        if QMessageBox.question(self, "Eliminar Entrada", "¿Está seguro?") != QMessageBox.StandardButton.Yes:
            return
        prod = self.sesion.query(Producto).filter_by(id=entrada.producto_id).first()
        if prod:
            prod.stock -= entrada.cantidad
        self.sesion.delete(entrada)
        self.sesion.commit()
        self.cargar_inventario()

class VentanaVentas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setLayout(QVBoxLayout())
        if not self.obtener_caja_abierta():
            QMessageBox.warning(self, "Caja", "La caja no está abierta. Abra la caja antes de vender.")
        self.busquedaLineEdit = QLineEdit()
        self.busquedaLineEdit.setPlaceholderText("Buscar producto para vender...")
        self.busquedaLineEdit.textChanged.connect(self.solicitarProductos)
        self.layout().addWidget(self.busquedaLineEdit)
        formLayout = QHBoxLayout()
        self.comboProducto = QComboBox()
        self.solicitarProductos()
        self.spinCantidad = QSpinBox()
        self.spinCantidad.setMinimum(1)
        btnAgregar = QPushButton("Agregar al Carrito")
        btnAgregar.clicked.connect(self.agregar_carrito)
        formLayout.addWidget(QLabel("Producto:"))
        formLayout.addWidget(self.comboProducto)
        formLayout.addWidget(QLabel("Cantidad:"))
        formLayout.addWidget(self.spinCantidad)
        formLayout.addWidget(btnAgregar)
        self.layout().addLayout(formLayout)
        self.tablaCarrito = QTableWidget()
        self.tablaCarrito.setColumnCount(4)
        self.tablaCarrito.setHorizontalHeaderLabels(["Producto", "Cantidad", "Precio Venta", "Subtotal"])
        header = self.tablaCarrito.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablaCarrito.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablaCarrito.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout().addWidget(self.tablaCarrito)
        totalLayout = QHBoxLayout()
        self.labelTotal = QLabel("Total: 0.00")
        btnVenta = QPushButton("Realizar Venta")
        btnVenta.clicked.connect(self.realizar_venta)
        totalLayout.addWidget(self.labelTotal)
        totalLayout.addStretch()
        totalLayout.addWidget(btnVenta)
        self.layout().addLayout(totalLayout)
        self.carrito = []

    def obtener_caja_abierta(self):
        return self.sesion.query(Caja).filter(Caja.fecha_cierre == None).first()

    def solicitarProductos(self):
        busqueda = self.busquedaLineEdit.text().strip().lower()
        self.comboProducto.clear()
        productos = self.sesion.query(Producto).all()
        if busqueda:
            productos = [p for p in productos if busqueda in p.nombre.lower()]
        for prod in productos:
            self.comboProducto.addItem(f"{prod.nombre} (Stock: {prod.stock})", prod.id)

    def agregar_carrito(self):
        if not self.obtener_caja_abierta():
            QMessageBox.warning(self, "Caja", "La caja no está abierta.")
            return
        prod_id = self.comboProducto.currentData()
        cantidad = self.spinCantidad.value()
        producto = self.sesion.query(Producto).filter_by(id=prod_id).first()
        if not producto:
            QMessageBox.warning(self, "Error", "Producto no encontrado")
            return
        if cantidad > producto.stock:
            QMessageBox.warning(self, "Error", f"Stock insuficiente para {producto.nombre}")
            return
        precio = float(producto.precio_venta)
        subtotal = precio * cantidad
        for item in self.carrito:
            if item["producto"].id == prod_id:
                item["cantidad"] += cantidad
                item["subtotal"] = item["cantidad"] * precio
                break
        else:
            self.carrito.append({"producto": producto, "cantidad": cantidad, "precio": precio, "subtotal": subtotal})
        self.actualizar_tabla_carrito()

    def actualizar_tabla_carrito(self):
        self.tablaCarrito.setRowCount(len(self.carrito))
        total = 0
        for i, item in enumerate(self.carrito):
            self.tablaCarrito.setItem(i, 0, QTableWidgetItem(item["producto"].nombre))
            self.tablaCarrito.setItem(i, 1, QTableWidgetItem(str(item["cantidad"])))
            self.tablaCarrito.setItem(i, 2, QTableWidgetItem(str(item["precio"])))
            self.tablaCarrito.setItem(i, 3, QTableWidgetItem(str(item["subtotal"])))
            total += item["subtotal"]
        self.labelTotal.setText(f"Total: {total:.2f}")

    def realizar_venta(self):
        if not self.obtener_caja_abierta():
            QMessageBox.warning(self, "Caja", "La caja no está abierta.")
            return
        if not self.carrito:
            QMessageBox.warning(self, "Error", "El carrito está vacío")
            return
        total = sum(item["subtotal"] for item in self.carrito)
        caja = self.obtener_caja_abierta()
        venta = Venta(total=total, caja_id=caja.id)
        self.sesion.add(venta)
        self.sesion.commit()
        for item in self.carrito:
            prod = self.sesion.query(Producto).filter_by(id=item["producto"].id).first()
            if item["cantidad"] > prod.stock:
                QMessageBox.warning(self, "Error", f"Stock insuficiente para {prod.nombre}")
                return
            prod.stock -= item["cantidad"]
            detalle = DetalleVenta(venta_id=venta.id, producto_id=prod.id, cantidad=item["cantidad"], subtotal=item["subtotal"])
            self.sesion.add(detalle)
        self.sesion.commit()
        QMessageBox.information(self, "Venta Realizada", f"Venta realizada. Total: {total:.2f}")
        generar_reporte_excel_venta(venta)
        self.carrito = []
        self.actualizar_tabla_carrito()
        self.solicitarProductos()

def generar_reporte_excel_venta(venta):
    session = SessionLocal()
    venta_info = {
        "Venta ID": venta.id,
        "Fecha": venta.fecha.strftime("%Y-%m-%d %H:%M:%S"),
        "Total": float(venta.total)
    }
    df_venta = pd.DataFrame([venta_info])
    query = session.query(DetalleVenta, Producto)\
        .join(Producto, Producto.id == DetalleVenta.producto_id)\
        .filter(DetalleVenta.venta_id == venta.id).all()
    detalle_list = []
    for detalle, producto in query:
        detalle_list.append({
            "Producto": producto.nombre,
            "Cantidad": detalle.cantidad,
            "Precio Venta": float(producto.precio_venta),
            "Subtotal": float(detalle.subtotal)
        })
    df_detalle = pd.DataFrame(detalle_list)
    if not df_detalle.empty:
        df_productos = df_detalle.groupby("Producto", as_index=False)\
            .agg({"Cantidad": "sum", "Subtotal": "sum"})\
            .rename(columns={"Cantidad": "Cantidad Total", "Subtotal": "Total Ventas"})
    else:
        df_productos = pd.DataFrame(columns=["Producto", "Cantidad Total", "Total Ventas"])
    filename, _ = QFileDialog.getSaveFileName(None, "Guardar reporte Excel de Venta", "", "Excel Files (*.xlsx)")
    if filename:
        try:
            with pd.ExcelWriter(filename, engine="openpyxl") as writer:
                df_venta.to_excel(writer, sheet_name="Venta", index=False)
                df_detalle.to_excel(writer, sheet_name="Detalle Venta", index=False)
                df_productos.to_excel(writer, sheet_name="Productos Vendidos", index=False)
            QMessageBox.information(None, "Reporte Excel", "Reporte de venta generado exitosamente.")
        except Exception as e:
            QMessageBox.warning(None, "Reporte Excel", f"Error al exportar: {str(e)}")
    session.close()

class VentanaVentasRealizadas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setLayout(QVBoxLayout())
        self.tablaVentas = QTableWidget()
        self.tablaVentas.setColumnCount(7)
        self.tablaVentas.setHorizontalHeaderLabels(["Venta ID", "Fecha", "Total", "Producto ID", "Producto", "Cantidad", "Subtotal"])
        header = self.tablaVentas.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablaVentas.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablaVentas.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout().addWidget(self.tablaVentas)
        self.cargar_ventas()

    def cargar_ventas(self):
        query = self.sesion.query(Venta, DetalleVenta, Producto)\
            .join(DetalleVenta, Venta.id == DetalleVenta.venta_id)\
            .join(Producto, Producto.id == DetalleVenta.producto_id).all()
        self.tablaVentas.setRowCount(len(query))
        for i, (venta, detalle, producto) in enumerate(query):
            self.tablaVentas.setItem(i, 0, QTableWidgetItem(str(venta.id)))
            self.tablaVentas.setItem(i, 1, QTableWidgetItem(venta.fecha.strftime("%Y-%m-%d %H:%M:%S")))
            self.tablaVentas.setItem(i, 2, QTableWidgetItem(str(venta.total)))
            self.tablaVentas.setItem(i, 3, QTableWidgetItem(str(producto.id)))
            self.tablaVentas.setItem(i, 4, QTableWidgetItem(producto.nombre))
            self.tablaVentas.setItem(i, 5, QTableWidgetItem(str(detalle.cantidad)))
            self.tablaVentas.setItem(i, 6, QTableWidgetItem(str(detalle.subtotal)))

class VentanaCaja(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setWindowTitle("Caja")
        self.layout = QVBoxLayout(self)
        self.caja_abierta = self.obtener_caja_abierta()
        if self.caja_abierta:
            self.labelInfo = QLabel(
                f"Caja abierta desde: {self.caja_abierta.fecha_apertura.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Monto Apertura: {self.caja_abierta.monto_apertura:.2f}"
            )
            self.layout.addWidget(self.labelInfo)
            self.inputMontoCierre = QLineEdit()
            self.inputMontoCierre.setPlaceholderText("Ingrese Monto Cierre (opcional)")
            self.layout.addWidget(self.inputMontoCierre)
            self.btnCerrarCaja = QPushButton("Cerrar Caja")
            self.btnCerrarCaja.clicked.connect(self.cerrar_caja)
            self.layout.addWidget(self.btnCerrarCaja)
        else:
            self.labelInfo = QLabel("Caja cerrada. Ingrese monto de apertura:")
            self.inputMonto = QLineEdit()
            self.btnAbrirCaja = QPushButton("Abrir Caja")
            self.btnAbrirCaja.clicked.connect(self.abrir_caja)
            self.layout.addWidget(self.labelInfo)
            self.layout.addWidget(self.inputMonto)
            self.layout.addWidget(self.btnAbrirCaja)

    def obtener_caja_abierta(self):
        return self.sesion.query(Caja).filter(Caja.fecha_cierre == None).first()

    def abrir_caja(self):
        try:
            monto = float(self.inputMonto.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Monto inválido")
            return
        caja = Caja(monto_apertura=monto)
        self.sesion.add(caja)
        self.sesion.commit()
        QMessageBox.information(self, "Caja", "Caja abierta exitosamente.")
        self.accept()

    def cerrar_caja(self):
        caja = self.caja_abierta
        if not caja:
            QMessageBox.warning(self, "Error", "No hay caja abierta.")
            return
        try:
            if self.inputMontoCierre.text().strip() == "":
                hoy = datetime.now()
                ventas = self.sesion.query(Venta).filter(
                    Venta.caja_id == caja.id,
                    Venta.fecha >= caja.fecha_apertura,
                    Venta.fecha <= hoy
                ).all()
                total = sum(v.total for v in ventas)
                saldo_final = float(caja.monto_apertura) + total
                monto_cierre = saldo_final
            else:
                monto_cierre = float(self.inputMontoCierre.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Monto Cierre inválido")
            return
        hoy = datetime.now()
        ventas = self.sesion.query(Venta).filter(
            Venta.caja_id == caja.id,
            Venta.fecha >= caja.fecha_apertura,
            Venta.fecha <= hoy
        ).all()
        total = sum(v.total for v in ventas)
        caja.total_ventas = total
        caja.fecha_cierre = hoy
        caja.monto_cierre = monto_cierre
        self.sesion.commit()
        QMessageBox.information(self, "Caja", f"Caja cerrada. Total ventas: {total:.2f}. Monto Cierre: {monto_cierre:.2f}")
        preview_dialog = ReportePreviewDialog(caja, self)
        preview_dialog.exec()
        self.accept()

class VentanaCajaModule(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        layout = QVBoxLayout(self)
        self.tablaCaja = QTableWidget()
        self.tablaCaja.setColumnCount(5)
        self.tablaCaja.setHorizontalHeaderLabels(["Caja ID", "Apertura", "Cierre", "Monto Apertura", "Total Ventas"])
        header = self.tablaCaja.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablaCaja.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablaCaja.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.tablaCaja)
        self.btnCaja = QPushButton()
        self.btnCaja.clicked.connect(self.accion_caja)
        layout.addWidget(self.btnCaja)
        self.btnPrevisualizar = QPushButton("Previsualización")
        self.btnPrevisualizar.clicked.connect(self.previsualizar_reporte)
        layout.addWidget(self.btnPrevisualizar)
        self.actualizar()

    def actualizar(self):
        cajas = self.sesion.query(Caja).filter(Caja.fecha_cierre != None).all()
        self.tablaCaja.setRowCount(len(cajas))
        for i, caja in enumerate(cajas):
            self.tablaCaja.setItem(i, 0, QTableWidgetItem(str(caja.id)))
            self.tablaCaja.setItem(i, 1, QTableWidgetItem(caja.fecha_apertura.strftime("%Y-%m-%d %H:%M:%S")))
            self.tablaCaja.setItem(i, 2, QTableWidgetItem(caja.fecha_cierre.strftime("%Y-%m-%d %H:%M:%S")))
            self.tablaCaja.setItem(i, 3, QTableWidgetItem(str(caja.monto_apertura)))
            self.tablaCaja.setItem(i, 4, QTableWidgetItem(str(caja.total_ventas if caja.total_ventas else 0)))
        openCaja = self.sesion.query(Caja).filter(Caja.fecha_cierre == None).first()
        if openCaja:
            self.btnCaja.setText("Cerrar Caja")
        else:
            self.btnCaja.setText("Abrir Caja")

    def accion_caja(self):
        dialog = VentanaCaja(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.actualizar()

    def previsualizar_reporte(self):
        fila = self.tablaCaja.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Seleccione una caja para previsualizar su reporte.")
            return
        caja_id = int(self.tablaCaja.item(fila, 0).text())
        caja = self.sesion.query(Caja).filter_by(id=caja_id).first()
        if not caja:
            QMessageBox.warning(self, "Error", "No se encontró la caja seleccionada.")
            return
        preview_dialog = ReportePreviewDialog(caja, self)
        preview_dialog.exec()

class VentanaDevoluciones(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sesion = SessionLocal()
        self.setLayout(QVBoxLayout())
        self.tablaDevoluciones = QTableWidget()
        self.tablaDevoluciones.setColumnCount(4)
        self.tablaDevoluciones.setHorizontalHeaderLabels(["Venta ID", "Fecha", "Total", "Estado"])
        header = self.tablaDevoluciones.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tablaDevoluciones.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tablaDevoluciones.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.layout().addWidget(self.tablaDevoluciones)
        btnCancelarVenta = QPushButton("Cancelar Venta")
        btnCancelarVenta.clicked.connect(self.cancelar_venta)
        self.layout().addWidget(btnCancelarVenta)
        self.cargar_devoluciones()

    def cargar_devoluciones(self):
        ventas = self.sesion.query(Venta).filter(Venta.caja_id != None).all()
        self.tablaDevoluciones.setRowCount(len(ventas))
        for i, v in enumerate(ventas):
            cancelacion = self.sesion.query(VentaCancelada).filter_by(venta_id=v.id).first()
            estado = "Cancelada" if cancelacion else "Activa"
            self.tablaDevoluciones.setItem(i, 0, QTableWidgetItem(str(v.id)))
            self.tablaDevoluciones.setItem(i, 1, QTableWidgetItem(v.fecha.strftime("%Y-%m-%d %H:%M:%S")))
            self.tablaDevoluciones.setItem(i, 2, QTableWidgetItem(str(v.total)))
            self.tablaDevoluciones.setItem(i, 3, QTableWidgetItem(estado))

    def cancelar_venta(self):
        fila = self.tablaDevoluciones.currentRow()
        if fila < 0:
            QMessageBox.warning(self, "Aviso", "Selecciona una venta para cancelar")
            return
        venta_id = int(self.tablaDevoluciones.item(fila, 0).text())
        venta = self.sesion.query(Venta).filter_by(id=venta_id).first()
        if not venta:
            QMessageBox.warning(self, "Error", "Venta no encontrada")
            return
        if QMessageBox.question(self, "Cancelar Venta", "¿Está seguro de cancelar esta venta? Esto eliminará la venta.") != QMessageBox.StandardButton.Yes:
            return
        if venta.caja_id:
            caja = self.sesion.query(Caja).filter_by(id=venta.caja_id).first()
            if caja and caja.total_ventas:
                caja.total_ventas -= venta.total
                if caja.total_ventas < 0:
                    caja.total_ventas = 0
        detalles = self.sesion.query(DetalleVenta).filter_by(venta_id=venta.id).all()
        for d in detalles:
            prod = self.sesion.query(Producto).filter_by(id=d.producto_id).first()
            if prod:
                prod.stock += d.cantidad
            self.sesion.delete(d)
        self.sesion.delete(venta)
        self.sesion.commit()
        QMessageBox.information(self, "Cancelación", "Venta cancelada y eliminada, stock reabastecido.")
        self.cargar_devoluciones()

class MainMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mainWindow = parent
        layout = QGridLayout(self)
        modules = [
            ("Inventario", self.mainWindow.mostrar_productos),
            ("Realizar Venta", self.mainWindow.mostrar_ventas),
            ("Agregar Stock", self.mainWindow.mostrar_inventario),
            ("Ventas Realizadas", self.mainWindow.mostrar_ventas_realizadas),
            ("Caja", self.mainWindow.mostrar_caja),
            ("Devoluciones", self.mainWindow.mostrar_devoluciones)
        ]
        row, col = 0, 0
        for label, callback in modules:
            btn = QPushButton(label)
            btn.setMinimumSize(200, 150)
            btn.setFont(QFont("Arial", 16, QFont.Weight.Bold))
            btn.clicked.connect(callback)
            layout.addWidget(btn, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Salus JJV - Sistema de Ventas")
        self.setWindowIcon(QIcon("icon.ico"))
        self.setGeometry(100, 100, 1000, 600)
        self.init_ui()
        self.showMaximized()

    def init_ui(self):
        archivo_menu = self.menuBar().addMenu("Archivo")
        salir_action = QAction("Salir", self)
        salir_action.triggered.connect(self.close)
        archivo_menu.addAction(salir_action)
        modulos_menu = self.menuBar().addMenu("Módulos")
        productos_action = QAction("Inventario", self)
        productos_action.triggered.connect(self.mostrar_productos)
        ventas_action = QAction("Realizar Venta", self)
        ventas_action.triggered.connect(self.mostrar_ventas)
        inventario_action = QAction("Agregar Stock", self)
        inventario_action.triggered.connect(self.mostrar_inventario)
        ventas_realizadas_action = QAction("Ventas Realizadas", self)
        ventas_realizadas_action.triggered.connect(self.mostrar_ventas_realizadas)
        caja_action = QAction("Caja", self)
        caja_action.triggered.connect(self.mostrar_caja)
        devoluciones_action = QAction("Devoluciones", self)
        devoluciones_action.triggered.connect(self.mostrar_devoluciones)
        usuarios_action = QAction("Usuarios", self)
        usuarios_action.triggered.connect(lambda: QMessageBox.information(self, "Usuarios", "Módulo en construcción"))
        modulos_menu.addAction(productos_action)
        modulos_menu.addAction(ventas_action)
        modulos_menu.addAction(inventario_action)
        modulos_menu.addAction(ventas_realizadas_action)
        modulos_menu.addAction(caja_action)
        modulos_menu.addAction(devoluciones_action)
        modulos_menu.addAction(usuarios_action)
        ayuda_menu = self.menuBar().addMenu("Ayuda")
        acerca_action = QAction("Acerca de", self)
        acerca_action.triggered.connect(lambda: QMessageBox.information(self, "Acerca de", "Salus JJV\nVersión 1.0"))
        exportar_db_action = QAction("Exportar Base de Datos", self)
        exportar_db_action.triggered.connect(exportar_base_datos_json)
        ayuda_menu.addAction(acerca_action)
        ayuda_menu.addAction(exportar_db_action)
        self.mostrar_main_menu()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.mostrar_main_menu()
        else:
            super().keyPressEvent(event)

    def mostrar_main_menu(self):
        self.setCentralWidget(MainMenu(self))

    def mostrar_productos(self):
        self.setCentralWidget(VentanaProductos(self))

    def mostrar_inventario(self):
        self.setCentralWidget(VentanaInventario(self))

    def mostrar_ventas(self):
        self.setCentralWidget(VentanaVentas(self))

    def mostrar_ventas_realizadas(self):
        self.setCentralWidget(VentanaVentasRealizadas(self))

    def mostrar_caja(self):
        self.setCentralWidget(VentanaCajaModule(self))

    def mostrar_devoluciones(self):
        self.setCentralWidget(VentanaDevoluciones(self))

def exportar_base_datos_json():
    session = SessionLocal()
    data = {}
    models = [Producto, InventarioEntry, Venta, DetalleVenta, Caja, VentaCancelada]
    for model in models:
        table_name = model.__tablename__
        items = session.query(model).all()
        data[table_name] = [{col.name: getattr(item, col.name) for col in model.__table__.columns} for item in items]
    filename, _ = QFileDialog.getSaveFileName(None, "Exportar Base de Datos", "", "JSON Files (*.json)")
    if filename:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, default=str)
            QMessageBox.information(None, "Exportar Base de Datos", "Base de datos exportada exitosamente.")
        except Exception as e:
            QMessageBox.warning(None, "Exportar Base de Datos", f"Error al exportar: {str(e)}")
    session.close()

def main():
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
