# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Adjacent Dissolve & Line Processor for QGIS
                              -------------------
        begin                : 2025-12-12
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Salvatore Fiandaca
        email                : pigrecoinfinito@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

"""
***************************************************************************
*                                                                         *
*   Dissolve Adjacent Polygons by Expression                            *
*   Algoritmo Processing per QGIS                                        *
*                                                                         *
*   Dissolve poligoni adiacenti basandosi su un'espressione applicata   *
*   all'attributo "note"                                                 *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterExpression,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterString,
    QgsFeatureSink,
    QgsFeature,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsProcessingException,
    QgsExpression,
    QgsExpressionContext,
    QgsExpressionContextUtils,
    QgsPointXY
)
from PyQt5.QtCore import QVariant


class DissolveAdjacentByExpressionAlgorithm(QgsProcessingAlgorithm):
    """
    Dissolve poligoni adiacenti basandosi su un'espressione applicata
    all'attributo "note".
    """

    # Costanti per i parametri
    INPUT = 'INPUT'
    EXPRESSION = 'EXPRESSION'
    USE_FILTER = 'USE_FILTER'
    FILTER_PREFIXES = 'FILTER_PREFIXES'
    USE_DUPLICATE_EXCEPTION = 'USE_DUPLICATE_EXCEPTION'
    EXCEPTION_VALUES = 'EXCEPTION_VALUES'
    OUTPUT_FILTERED = 'OUTPUT_FILTERED'
    OUTPUT = 'OUTPUT'
    OUTPUT_LINES = 'OUTPUT_LINES'
    OUTPUT_LINES_DISSOLVED = 'OUTPUT_LINES_DISSOLVED'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DissolveAdjacentByExpressionAlgorithm()

    def name(self):
        return 'dissolveadjacentbyexpression'

    def displayName(self):
        return self.tr('Dissolve Adjacent by Expression')

    def group(self):
        return self.tr('Vector geometry')

    def groupId(self):
        return 'vectorgeometry'

    def shortHelpString(self):
        return self.tr("""
        <h3>Dissolve Adjacent by Expression</h3>
        
        <p>Dissolve poligoni adiacenti con la stessa espressione e genera layer lineari dai bordi.</p>
        
        <h4>Parametri</h4>
        <ul>
        <li><b>Input layer:</b> Layer poligonale con attributo "note"</li>
        <li><b>Expression:</b> Espressione per raggruppare (es: <code>regexp_substr("note",'(^.+\\d\\|)')</code>)</li>
        <li><b>Apply prefix filter:</b> Filtra per prefissi specifici (opzionale)</li>
        <li><b>Filter prefixes:</b> Lista separata da virgole (default: CEC,PdCC,PdC,PEC,PI,PR.CS,Suevig)</li>
        <li><b>Keep duplicates for specific values:</b> Attiva eccezioni per duplicati (opzionale)</li>
        <li><b>Exception values:</b> Valori per cui gestire duplicati in modo speciale</li>
        </ul>
        
        <h4>Logica Eccezioni Duplicati</h4>
        <p>Quando attivata, controlla la presenza del valore di eccezione in "note" dei segmenti duplicati:</p>
        <ul>
        <li><b>Eccezione in NESSUNO:</b> elimina duplicato (normale)</li>
        <li><b>Eccezione in UNO SOLO:</b> mantieni entrambi i segmenti</li>
        <li><b>Eccezione in ENTRAMBI:</b> elimina duplicato</li>
        </ul>
        
        <h4>Output</h4>
        <ol>
        <li><b>Filtered polygons:</b> Poligoni dopo il filtro (se applicato)</li>
        <li><b>Dissolved polygons:</b> Poligoni dissolti single-part</li>
        <li><b>Lines without duplicates:</b> Segmenti dai bordi senza duplicati geometrici</li>
        <li><b>Lines dissolved by attributes:</b> Segmenti dissolti per (note, nro, id)</li>
        --------------
        <li><b>Autore:</b> Salvatore Fiandaca - 2025</li>
        </ol>
        """)

    def initAlgorithm(self, config=None):
        # Input layer
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        # Filtro - prima il campo con i valori
        self.addParameter(
            QgsProcessingParameterString(
                self.FILTER_PREFIXES,
                self.tr('Filter prefixes (comma-separated)'),
                defaultValue='CEC,PdCC,PdC,PEC,PI,PR.CS,Suevig',
                optional=True
            )
        )

        # Poi la checkbox per attivarlo
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_FILTER,
                self.tr('Apply prefix filter'),
                defaultValue=False
            )
        )

        # Espressione
        self.addParameter(
            QgsProcessingParameterExpression(
                self.EXPRESSION,
                self.tr('Expression'),
                defaultValue='regexp_substr("note",\'(^.+\\\\d\\\\|)\')',
                parentLayerParameterName=self.INPUT
            )
        )

        # Eccezioni duplicati - prima il campo con i valori
        self.addParameter(
            QgsProcessingParameterString(
                self.EXCEPTION_VALUES,
                self.tr('Exception values in "note" (comma-separated, case-insensitive)'),
                defaultValue='',
                optional=True
            )
        )

        # Poi la checkbox per attivarle
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.USE_DUPLICATE_EXCEPTION,
                self.tr('Keep duplicates for specific values'),
                defaultValue=False
            )
        )

        # Output filtrato
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_FILTERED,
                self.tr('Filtered polygons'),
                optional=True
            )
        )

        # Output poligonale
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Dissolved polygons')
            )
        )

        # Output lineare
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Lines without duplicates')
            )
        )

        # Output lineare dissolto
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES_DISSOLVED,
                self.tr('Lines dissolved by attributes')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        # Ottieni parametri
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT)
            )

        expression_text = self.parameterAsExpression(parameters, self.EXPRESSION, context)
        use_filter = self.parameterAsBoolean(parameters, self.USE_FILTER, context)
        filter_prefixes_text = self.parameterAsString(parameters, self.FILTER_PREFIXES, context)
        use_duplicate_exception = self.parameterAsBoolean(parameters, self.USE_DUPLICATE_EXCEPTION, context)
        exception_values_text = self.parameterAsString(parameters, self.EXCEPTION_VALUES, context)
        
        exception_values = []
        if use_duplicate_exception and exception_values_text:
            exception_values = [v.strip().upper() for v in exception_values_text.split(',') if v.strip()]
            feedback.pushInfo(self.tr('Eccezioni duplicati: {}').format(', '.join(exception_values)))

        # Verifica attributo "note"
        if source.fields().indexOf('note') == -1:
            raise QgsProcessingException(
                self.tr('Il layer di input non contiene l\'attributo "note"')
            )

        # Prepara fields output (note, nro, id)
        fields = QgsFields()
        note_field = source.fields().field('note')
        fields.append(QgsField('note', note_field.type()))
        fields.append(QgsField('nro', QVariant.Int))
        fields.append(QgsField('id', QVariant.Int))

        # Crea sinks
        (sink_poly, dest_id_poly) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.Polygon, source.sourceCrs()
        )

        (sink_lines, dest_id_lines) = self.parameterAsSink(
            parameters, self.OUTPUT_LINES, context, fields,
            QgsWkbTypes.LineString, source.sourceCrs()
        )

        (sink_lines_dissolved, dest_id_lines_dissolved) = self.parameterAsSink(
            parameters, self.OUTPUT_LINES_DISSOLVED, context, fields,
            QgsWkbTypes.MultiLineString, source.sourceCrs()
        )

        # STEP 1: Filtra features (opzionale)
        features = list(source.getFeatures())
        sink_filtered = None
        dest_id_filtered = None

        if use_filter and filter_prefixes_text:
            filter_prefixes = [p.strip() for p in filter_prefixes_text.split(',')]
            (sink_filtered, dest_id_filtered) = self.parameterAsSink(
                parameters, self.OUTPUT_FILTERED, context,
                source.fields(), source.wkbType(), source.sourceCrs()
            )

            filter_exp = QgsExpression('regexp_substr("note", \'(^.+\\\\d)\')')
            exp_context = QgsExpressionContext()
            exp_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(None))
            
            filtered_features = []
            for feature in features:
                exp_context.setFeature(feature)
                prefix_value = filter_exp.evaluate(exp_context)
                if prefix_value:
                    prefix_str = str(prefix_value).upper()
                    if any(prefix_str.startswith(p.upper()) for p in filter_prefixes):
                        filtered_features.append(feature)
                        if sink_filtered:
                            sink_filtered.addFeature(feature, QgsFeatureSink.FastInsert)
            
            features = filtered_features
            feedback.pushInfo(self.tr('Features filtrate: {}').format(len(features)))

        # STEP 2: Dissolve poligonale
        dissolved_polygons = self.dissolve_polygons(features, expression_text, feedback, context)
        
        # STEP 3: Converti a single-part e scrivi output poligonale
        unique_id = 1
        all_polygons_with_id = []
        
        for dissolved_geom, note_val, nro_val in dissolved_polygons:
            if dissolved_geom.isMultipart():
                parts = dissolved_geom.asGeometryCollection()
                for part in parts:
                    out_feature = QgsFeature(fields)
                    out_feature.setGeometry(part)
                    out_feature['note'] = note_val
                    out_feature['nro'] = nro_val
                    out_feature['id'] = unique_id
                    sink_poly.addFeature(out_feature, QgsFeatureSink.FastInsert)
                    all_polygons_with_id.append((part, note_val, nro_val, unique_id))
                    unique_id += 1
            else:
                out_feature = QgsFeature(fields)
                out_feature.setGeometry(dissolved_geom)
                out_feature['note'] = note_val
                out_feature['nro'] = nro_val
                out_feature['id'] = unique_id
                sink_poly.addFeature(out_feature, QgsFeatureSink.FastInsert)
                all_polygons_with_id.append((dissolved_geom, note_val, nro_val, unique_id))
                unique_id += 1

        feedback.pushInfo(self.tr('Poligoni dissolti: {}').format(len(all_polygons_with_id)))

        # STEP 4: Converti poligoni in linee (boundary)
        lines_with_attrs = []
        for poly_geom, note_val, nro_val, id_val in all_polygons_with_id:
            # Estrai il boundary dalla geometria
            geom_const = poly_geom.constGet()
            if geom_const:
                boundary = geom_const.boundary()
                if boundary:
                    boundary_geom = QgsGeometry(boundary)
                    lines_with_attrs.append((boundary_geom, note_val, nro_val, id_val))

        feedback.pushInfo(self.tr('Linee estratte: {}').format(len(lines_with_attrs)))

        # STEP 5: Esplodi linee in segmenti
        all_segments = []
        for line_geom, note_val, nro_val, id_val in lines_with_attrs:
            segments = self.explode_line_to_segments(line_geom, note_val, nro_val, id_val)
            all_segments.extend(segments)

        feedback.pushInfo(self.tr('Segmenti totali: {}').format(len(all_segments)))

        # STEP 6: Elimina duplicati geometrici
        unique_segments = self.remove_duplicate_segments(all_segments, exception_values, feedback)

        feedback.pushInfo(self.tr('Segmenti unici: {}').format(len(unique_segments)))

        # STEP 7: Scrivi segmenti in Lines without duplicates
        for seg_geom, note_val, nro_val, id_val in unique_segments:
            out_feature = QgsFeature(fields)
            out_feature.setGeometry(seg_geom)
            out_feature['note'] = note_val
            out_feature['nro'] = nro_val
            out_feature['id'] = id_val
            sink_lines.addFeature(out_feature, QgsFeatureSink.FastInsert)

        # STEP 8: Dissolve segmenti per (note, nro, id)
        self.dissolve_lines_by_attributes(unique_segments, sink_lines_dissolved, fields, feedback)

        feedback.pushInfo(self.tr('Processing completato!'))

        result = {
            self.OUTPUT: dest_id_poly,
            self.OUTPUT_LINES: dest_id_lines,
            self.OUTPUT_LINES_DISSOLVED: dest_id_lines_dissolved
        }
        if dest_id_filtered:
            result[self.OUTPUT_FILTERED] = dest_id_filtered

        return result

    def dissolve_polygons(self, features, expression_text, feedback, context):
        """Dissolve poligoni per espressione e adiacenza."""
        exp = QgsExpression(expression_text)
        exp_context = QgsExpressionContext()
        exp_context.appendScopes(QgsExpressionContextUtils.globalProjectLayerScopes(None))

        # Raggruppa per valore espressione
        groups = {}
        for feature in features:
            exp_context.setFeature(feature)
            exp_value = str(exp.evaluate(exp_context)) if exp.evaluate(exp_context) is not None else 'NULL'
            if exp_value not in groups:
                groups[exp_value] = []
            groups[exp_value].append(feature)

        feedback.pushInfo(self.tr('Gruppi per espressione: {}').format(len(groups)))

        # Dissolve ogni gruppo
        dissolved_results = []
        for group_value, group_features in groups.items():
            if len(group_features) == 1:
                dissolved_results.append((
                    group_features[0].geometry(),
                    group_features[0]['note'],
                    1
                ))
            else:
                clusters = self.find_adjacent_clusters(group_features)
                for cluster in clusters:
                    note_values = list(dict.fromkeys([f['note'] for f in cluster]))
                    concatenated_note = ",".join(str(v) if v is not None else "" for v in note_values)
                    nro_count = len(note_values)
                    
                    geoms = [f.geometry() for f in cluster]
                    dissolved_geom = QgsGeometry.unaryUnion(geoms)
                    
                    if not dissolved_geom.isNull():
                        dissolved_results.append((dissolved_geom, concatenated_note, nro_count))

        return dissolved_results

    def find_adjacent_clusters(self, features):
        """Trova cluster di feature adiacenti."""
        clusters = []
        remaining = list(features)

        while remaining:
            current_cluster = [remaining.pop(0)]
            changed = True

            while changed and remaining:
                changed = False
                to_remove = []

                for i, candidate in enumerate(remaining):
                    for cluster_feature in current_cluster:
                        if candidate.geometry().touches(cluster_feature.geometry()):
                            current_cluster.append(candidate)
                            to_remove.append(i)
                            changed = True
                            break

                for i in reversed(to_remove):
                    remaining.pop(i)

            clusters.append(current_cluster)

        return clusters

    def explode_line_to_segments(self, line_geom, note_val, nro_val, id_val):
        """Esplode una linea in segmenti."""
        segments = []

        if line_geom.isMultipart():
            parts = line_geom.asMultiPolyline()
            for part in parts:
                for i in range(len(part) - 1):
                    seg_geom = QgsGeometry.fromPolylineXY([part[i], part[i+1]])
                    segments.append((seg_geom, note_val, nro_val, id_val))
        else:
            vertices = line_geom.asPolyline()
            for i in range(len(vertices) - 1):
                seg_geom = QgsGeometry.fromPolylineXY([vertices[i], vertices[i+1]])
                segments.append((seg_geom, note_val, nro_val, id_val))

        return segments

    def remove_duplicate_segments(self, all_segments, exception_values, feedback):
        """Elimina duplicati geometrici con gestione eccezioni."""
        segments_dict = {}

        for seg_geom, note_val, nro_val, id_val in all_segments:
            vertices = seg_geom.asPolyline()
            if len(vertices) != 2:
                continue

            seg_key = self.get_segment_key(vertices[0], vertices[1])

            if seg_key in segments_dict:
                existing_geom, existing_note, existing_nro, existing_id = segments_dict[seg_key]
                
                should_keep = False
                if exception_values:
                    current_upper = str(note_val).upper() if note_val else ""
                    existing_upper = str(existing_note).upper() if existing_note else ""
                    
                    exc_in_current = any(exc in current_upper for exc in exception_values)
                    exc_in_existing = any(exc in existing_upper for exc in exception_values)
                    
                    if exc_in_current != exc_in_existing:
                        should_keep = True

                if should_keep:
                    counter = 1
                    unique_key = (seg_key, counter)
                    while unique_key in segments_dict:
                        counter += 1
                        unique_key = (seg_key, counter)
                    segments_dict[unique_key] = (seg_geom, note_val, nro_val, id_val)
            else:
                segments_dict[seg_key] = (seg_geom, note_val, nro_val, id_val)

        return list(segments_dict.values())

    def get_segment_key(self, p1, p2):
        """Crea chiave univoca per segmento."""
        coords1 = (round(p1.x(), 6), round(p1.y(), 6))
        coords2 = (round(p2.x(), 6), round(p2.y(), 6))
        return (coords1, coords2) if coords1 < coords2 else (coords2, coords1)

    def dissolve_lines_by_attributes(self, segments, sink, fields, feedback):
        """Dissolve segmenti per (note, nro, id) usando linemerge."""
        groups = {}
        for seg_geom, note_val, nro_val, id_val in segments:
            key = (note_val, nro_val, id_val)
            if key not in groups:
                groups[key] = []
            groups[key].append(seg_geom)

        for (note_val, nro_val, id_val), geoms in groups.items():
            if len(geoms) == 1:
                merged_geom = geoms[0]
            else:
                # Raccogli prima in una MultiLineString
                multi_geom = QgsGeometry.collectGeometry(geoms)
                # Poi applica linemerge per unire segmenti connessi
                merged_geom = multi_geom.mergeLines()

            if merged_geom and not merged_geom.isNull():
                out_feature = QgsFeature(fields)
                out_feature.setGeometry(merged_geom)
                out_feature['note'] = note_val
                out_feature['nro'] = nro_val
                out_feature['id'] = id_val
                sink.addFeature(out_feature, QgsFeatureSink.FastInsert)

        feedback.pushInfo(self.tr('Linee dissolte: {}').format(len(groups)))
