# -*- coding: utf-8 -*-

"""
Utilidad para convertir números a texto en español (Ecuador)
Usado para convertir el monto del cheque a letras
"""

UNIDADES = (
    '', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE'
)

DECENAS = (
    'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS',
    'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE'
)

DECENAS_TENS = (
    '', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA',
    'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA'
)

CENTENAS = (
    '', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS'
)


def number_to_text_es(number, currency='DÓLARES'):
    """
    Convierte un número a texto en español
    
    Args:
        number: Número a convertir (float)
        currency: Nombre de la moneda (default: 'DÓLARES')
    
    Returns:
        str: Número convertido a texto
        
    Example:
        >>> number_to_text_es(125.50)
        'CIENTO VEINTICINCO DÓLARES CON 50/100'
    """
    if not isinstance(number, (int, float)):
        return ''
    
    # Mapear códigos de moneda a nombres completos
    currency_map = {
        'USD': 'DÓLARES',
        'EUR': 'EUROS',
        'COP': 'PESOS',
        'MXN': 'PESOS',
        'PEN': 'SOLES',
    }
    
    # Si es un código de moneda, convertirlo al nombre completo
    if currency in currency_map:
        currency = currency_map[currency]
    
    # Separar parte entera y decimal
    integer_part = int(abs(number))
    decimal_part = int(round((abs(number) - integer_part) * 100))
    
    # Convertir parte entera
    if integer_part == 0:
        text = 'CERO'
    else:
        text = _convert_number(integer_part)
    
    # Agregar moneda
    if integer_part == 1:
        # Singular: UN DÓLAR
        if currency.endswith('ES'):
            currency_singular = currency[:-2]  # DÓLARES -> DÓLAR
        elif currency.endswith('S'):
            currency_singular = currency[:-1]  # EUROS -> EURO, PESOS -> PESO
        else:
            currency_singular = currency
        text = f'{text} {currency_singular}'
    else:
        text = f'{text} {currency}'
    
    # Agregar parte decimal
    text = f'{text} CON {decimal_part:02d}/100'
    
    return text


def _convert_number(number):
    """
    Convierte la parte entera del número a texto
    """
    if number == 0:
        return 'CERO'
    
    if number < 0:
        return 'MENOS ' + _convert_number(-number)
    
    # Millones
    if number >= 1000000:
        millions = number // 1000000
        remainder = number % 1000000
        
        if millions == 1:
            text = 'UN MILLÓN'
        else:
            text = _convert_number(millions) + ' MILLONES'
        
        if remainder > 0:
            text += ' ' + _convert_number(remainder)
        
        return text
    
    # Miles
    if number >= 1000:
        thousands = number // 1000
        remainder = number % 1000
        
        if thousands == 1:
            text = 'MIL'
        else:
            text = _convert_number(thousands) + ' MIL'
        
        if remainder > 0:
            text += ' ' + _convert_number(remainder)
        
        return text
    
    # Centenas
    if number >= 100:
        hundreds = number // 100
        remainder = number % 100
        
        if number == 100:
            return 'CIEN'
        
        text = CENTENAS[hundreds]
        
        if remainder > 0:
            text += ' ' + _convert_number(remainder)
        
        return text
    
    # Decenas y unidades
    if number >= 20:
        tens = number // 10
        units = number % 10
        
        if units == 0:
            return DECENAS_TENS[tens]
        else:
            return DECENAS_TENS[tens] + ' Y ' + UNIDADES[units]
    
    # 10-19
    if number >= 10:
        return DECENAS[number - 10]
    
    # 1-9
    return UNIDADES[number]
