# SPDX-FileCopyrightText: 2021 Volker Krause <vkrause@kde.org>
# SPDX-License-Identifier: LGPL-2.0-or-later

from config import *
import io
import os
from qgis import *
from qgis.core import *

def tzIdToEnum(tzId):
    return tzId.replace('/', '_').replace('-', '_')

def normalizedTz(tzId):
    if tzId in TZID_MAP:
        return TZID_MAP[tzId]
    return tzId

def normalizedCountry(code):
    if code in ISO3166_1_MAP:
        return ISO3166_1_MAP[code]
    return code

# Generate IANA timezone names string table
# This allows us to reference timezones by a uint16_t in other data tables
class TimezoneStringTableTask(QgsTask):
    def __init__(self, context):
        super().__init__('Generate timezone string table', QgsTask.CanCancel)
        self.context = context

    def run(self):
        QgsMessageLog.logMessage('Generating timezone string table', LOG_CATEGORY, Qgis.Info)
        tzLayer = self.context['tzLayer']
        tzIds = set()
        for tz in tzLayer.getFeatures():
            tzIds.add(tz['tzid'])
        tzIds = list(tzIds)
        tzIds.sort()
        offsets = [0]

        out = open('../../data/timezone_name_table.cpp', 'w')
        out.write("""/*
 * SPDX-License-Identifier: ODbL-1.0
 * SPDX-FileCopyrightText: OpenStreetMap contributors
 *
 * Autogenerated using QGIS - do not edit!
 */

static constexpr const char timezone_name_table[] =
""")
        for tzId in tzIds:
            out.write(f"    \"{tzId}\\0\"\n")
            offsets.append(offsets[-1] + len(tzId) + 1)
        out.seek(out.tell() - 1, io.SEEK_SET) # to make clang-format happy
        out.write(";\n")
        out.close()

        out = open('../../data/timezone_names_p.h', 'w')
        out.write("""/*
 * SPDX-License-Identifier: ODbL-1.0
 * SPDX-FileCopyrightText: OpenStreetMap contributors
 *
 * Autogenerated using QGIS - do not edit!
 */

#ifndef TIMEZONE_NAMES_P_H
#define TIMEZONE_NAMES_P_H

#include <cstdint>

enum Tz : uint16_t {
""")
        for i in range(len(tzIds)):
            out.write(f"    {tzIdToEnum(tzIds[i])} = {offsets[i]},\n")
        out.write(f"    Undefined = {offsets[-1] - 1},\n") # points to the last null byte
        out.write("};\n\n#endif\n")
        out.close()
        return True

# Computes country/country subdivision to timezone mapping
class RegionToTimezoneMapTask(QgsTask):
    def __init__(self, context):
        super().__init__('Computing region to timezone mapping', QgsTask.CanCancel)
        self.context = context

    def run(self):
        QgsMessageLog.logMessage('Computing region to timezone mapping', LOG_CATEGORY, Qgis.Info)
        countryLayer = self.context['countryLayer']
        tzLayer = self.context['tzLayer']
        countryToTz = {}
        for country in countryLayer.getFeatures():
            countryCode = country['ISO3166-1']
            if not countryCode in countryToTz:
                countryToTz[countryCode] = set()
            countryGeom = country.geometry()
            countryArea = countryGeom.area()
            for tz in tzLayer.getFeatures():
                tzId = normalizedTz(tz['tzId'])
                if tz.geometry().intersects(countryGeom):
                    # filter out intersection noise along the boundaries
                    area = tz.geometry().intersection(countryGeom).area()
                    tzAreaRatio = area / tz.geometry().area()
                    countryAreaRatio = area / countryArea
                    if tzAreaRatio > 0.01 or countryAreaRatio > 0.1:
                        countryToTz[countryCode].add(tzId)

        out = open('../../data/country_timezone_map.cpp', 'w')
        out.write("""/*
 * SPDX-License-Identifier: ODbL-1.0
 * SPDX-FileCopyrightText: OpenStreetMap contributors
 *
 * Autogenerated using QGIS - do not edit!
 */

#include "isocodes_p.h"
#include "mapentry_p.h"
#include "timezone_names_p.h"

static constexpr const MapEntry<uint16_t> country_timezone_map[] = {
""")
        countries = list(countryToTz)
        countries.sort()
        for country in countries:
            if len(countryToTz[country]) == 1:
                out.write(f"    {{IsoCodes::alpha2CodeToKey(\"{country}\"), Tz::{tzIdToEnum(list(countryToTz[country])[0])}}},\n")

        out.write("};\n")
        out.close()

        # for countries with more than one tz, match against subdivisions
        subdivToTz = {}
        subdivLayer = self.context['subdivLayer']
        tzLayer = self.context['tzLayer']
        for subdiv in subdivLayer.getFeatures():
            code = subdiv['ISO3166-2']
            country = code[:2]
            if len(countryToTz[country]) <= 1:
                continue
            if not code in subdivToTz:
                subdivToTz[code] = {}
            subdivGeom = subdiv.geometry()
            subdivArea = subdivGeom.area()
            for tz in tzLayer.getFeatures():
                tzId = normalizedTz(tz['tzId'])
                if tz.geometry().intersects(subdivGeom):
                    # filter out intersection noise along the boundaries
                    area = tz.geometry().intersection(subdivGeom).area()
                    tzAreaRatio = area / tz.geometry().area()
                    subdivAreaRatio = area / subdivArea
                    if tzAreaRatio > 0.01 or subdivAreaRatio > 0.1:
                        if not tzId in subdivToTz[code]:
                            subdivToTz[code][tzId] = area
                        else:
                            subdivToTz[code][tzId] += area

        out = open('../../data/subdivision_timezone_map.cpp', 'w')
        out.write("""/*
 * SPDX-License-Identifier: ODbL-1.0
 * SPDX-FileCopyrightText: OpenStreetMap contributors
 *
 * Autogenerated using QGIS - do not edit!
 */

#include "isocodes_p.h"
#include "mapentry_p.h"
#include "timezone_names_p.h"

static constexpr const MapEntry<uint32_t> subdivision_timezone_map[] = {
""")
        subdivs = list(subdivToTz)
        subdivs.sort()
        for subdiv in subdivs:
            # sort by area, biggest one first
            tzs = list(subdivToTz[subdiv])
            tzs.sort(key = lambda x: subdivToTz[subdiv][x], reverse = True)
            for tz in tzs:
                out.write(f"    {{IsoCodes::subdivisionCodeToKey(\"{subdiv}\"), Tz::{tzIdToEnum(tz)}}},\n")
            if len(subdivToTz[subdiv]) == 0:
                out.write(f"    // {subdiv}\n")

        out.write("};\n")
        out.close()

        self.context['countryToTimezoneMap'] = countryToTz
        self.context['subdivisionToTimezoneMap'] = subdivToTz
        return True

# Compute timezone to country mapping
class TimezoneToCountryMapTask(QgsTask):
    def __init__(self, context):
        super().__init__('Computing timezone to country mapping', QgsTask.CanCancel)
        self.context = context

    def disambiguateCountries(self, countries):
        if len(countries) != 2:
            return countries
        for map in ISO3166_1_DISAMBIGUATION_MAP:
            if map[0] in countries and map[1] in countries:
                countries.remove(map[1])
                return countries
        return countries

    def run(self):
        QgsMessageLog.logMessage('Computing timezone to country mapping', LOG_CATEGORY, Qgis.Info)
        countryLayer = self.context['countryLayer']
        tzLayer = self.context['tzLayer']
        tzToCountry = {}
        for tz in tzLayer.getFeatures():
            tzId = tz['tzId'] # non-normalized!
            tzGeom = tz.geometry()
            tzArea = tzGeom.area()
            if not tz in tzToCountry:
                tzToCountry[tzId] = set()
            for country in countryLayer.getFeatures():
                code = normalizedCountry(country['ISO3166-1'])
                if code and country.geometry().intersects(tzGeom):
                    # filter out intersection noise along the boundaries
                    area = country.geometry().intersection(tzGeom).area()
                    tzAreaRatio = area / tzArea
                    countryAreaRatio = area / country.geometry().area()
                    if tzAreaRatio > 0.01 or countryAreaRatio > 0.1:
                        tzToCountry[tzId].add(code)

        out = open('../../data/timezone_country_map.cpp', 'w')
        out.write("""/*
 * SPDX-License-Identifier: ODbL-1.0
 * SPDX-FileCopyrightText: OpenStreetMap contributors
 *
 * Autogenerated using QGIS - do not edit!
 */

#include "isocodes_p.h"
#include "mapentry_p.h"
#include "timezone_names_p.h"

static constexpr const MapEntry<uint16_t> timezone_country_map[] = {
""")
        tzIds = list(tzToCountry)
        tzIds.sort()
        for tzId in tzIds:
            countries = self.disambiguateCountries(tzToCountry[tzId])
            if len(countries) == 1:
                out.write(f"    {{Tz::{tzIdToEnum(tzId)}, IsoCodes::alpha2CodeToKey(\"{list(countries)[0]}\")}},\n")
            else:
                out.write(f"    // Tz::{tzIdToEnum(tzId)}\n")
        out.write("};\n")
        out.close()
        return True