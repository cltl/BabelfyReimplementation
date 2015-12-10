
import logging
import os
import re
import sys

from lxml import etree


_log = logging.getLogger('evaluation')

    
records = []
log_records = []


def get_best_ref(entity_elem, resource):
    best_score = None
    best_ref = None
    for externalRef_elem in entity_elem.iter("externalRef"):
        if not resource or externalRef_elem.attrib['resource'] == resource:
            ref = externalRef_elem.attrib['reference']
            score = (float(externalRef_elem.get('confidence'))
                     if 'confidence' in externalRef_elem.attrib
                     else None)
            if not best_ref: # first one
                best_score = score
                best_ref = ref
            elif score and score > best_score:
                best_score = score
                best_ref = ref
    return best_ref


def get_span(entity_elem, root):
    words = []
    for term_target_elem in entity_elem.iter("target"):
        term_id = term_target_elem.get('id')
        term_elem = root.xpath(".//term[@id='%s']" %term_id)[0]
        for word_target_elem in term_elem.iter("target"):
            word_id = word_target_elem.get('id')
            word_elem = root.xpath(".//wf[@id='%s']" %word_id)[0]
            words.append((int(word_elem.get('offset')), int(word_elem.get('length'))))
    start = min(offset for offset, _ in words)
    end = max(offset+length for offset, length in words)
    return (start, end)


def get_tids(entity_elem, root):
    words = []
    for term_target_elem in entity_elem.iter("target"):
        term_id = term_target_elem.get('id')
        term_elem = root.xpath(".//term[@id='%s']" %term_id)[0]
        for word_target_elem in term_elem.iter("target"):
            word_id = word_target_elem.get('id')
            words.append(int(word_id.replace("w", "").replace("t", "")))
    start = min(x for x in words)
    end = max(x for x in words)
    print "STARTEND", start, end
    return (start, end)


def get_extrefs(path, resource):
    with open(path) as f:
        root = etree.parse(f).getroot()
    for entity_elem in root.iter("entity"):
        ref = get_best_ref(entity_elem, resource)
        if ref:
            ref=ref.replace("http://dbpedia.org/resource/", "").replace("http://DBpedia.org/resource/", "")
            span = get_tids(entity_elem, root)
            yield (span, ref)
        

def eval_file(tar, ref, tar_resource, ref_resource):
    tar_dict = dict(get_extrefs(tar, tar_resource))
    print tar_dict
    ref_dict = dict(get_extrefs(ref, ref_resource))
    print ref_dict
    dis_correct = sum(1 for span in tar_dict
                  if span in ref_dict and 
                  tar_dict[span] == ref_dict[span] and 
                  tar_dict[span] != '--NME--')
    dis_tar_total = sum(1 for span in tar_dict
                        if tar_dict[span] != '--NME--')
    dis_ref_total = sum(1 for span in ref_dict
                        if ref_dict[span] != '--NME--')
    reg_correct = sum(1 for span in tar_dict 
                       if span in ref_dict)
    fname = os.path.basename(tar)
    records.append((fname, dis_correct, dis_tar_total, dis_ref_total, reg_correct, len(tar_dict), len(ref_dict)))
    
    
def eval_log(log_path):
    global log_records
    fnames = []
    replaced_count = []
    with open(log_path) as f:
        for line in f:
            m1 = re.match("Processing file (.+)\n", line)
            if m1: fnames.append(m1.group(1))
            m2 = re.match("Reranking step replaced (\\d+)\n")
            if m2: replaced_count.append(int(m2.group(1)))
    log_records = zip(fnames, replaced_count)


def eval_dir(tar, ref, tar_resource, ref_resource):
    tar_files = set(os.listdir(tar))
    ref_files = set(os.listdir(ref))
    eval_files = tar_files.intersection(ref_files)
    if len(eval_files) < len(tar_files):
        _log.warn("These files won't be evaluated: %s" 
                  %', '.join(tar_files.difference(eval_files)))
    if len(eval_files) < len(ref_files):
        _log.warn("These gold standard files won't be used: %s" 
                  %', '.join(ref_files.difference(eval_files)))
    for fname in eval_files:
        _log.info("Evaluating file %s" %fname)
        try:
            tar_file = os.path.join(tar, fname)
            ref_file = os.path.join(ref, fname)
            eval_file(tar_file, ref_file, tar_resource, ref_resource)
        except KeyboardInterrupt:
            raise # avoid being suppressed
        except Exception as e:
            _log.exception("Error at file %s: %s" %(fname, str(e)))
    log_path = os.path.join(tar, "rerank.out")
    if not os.path.exists(log_path):
        log_path = os.path.join(tar, "rerank.log")
    if os.path.exists(log_path):
        eval_log(log_path)


def div(a, b):
    if b == 0:
        return float('NaN')
    return a/float(b)


def compute(dis_correct, dis_tar_total, dis_ref_total, reg_correct, reg_tar_total, reg_ref_total):
    dis_p = div(dis_correct, dis_tar_total) # precision
    dis_r = div(dis_correct, dis_ref_total) # recall
    dis_f1 = 2 / (1/dis_p + 1/dis_r) if dis_correct > 0 else 0
    reg_p = div(reg_correct, reg_tar_total) # span precision
    reg_r = div(reg_correct, reg_ref_total) # span recall
    reg_f1 = 2 / (1/reg_p + 1/reg_r) if reg_correct > 0 else 0
    return dis_p, dis_r, dis_f1, reg_p, reg_r, reg_f1
    

def write_detailed_report(path):
    _log.info("Writing detailed report...")
    with open(path, "wt") as f:
        f.write("fname\tdis_correct\tdis_tar\tdis_ref\treg_correct\treg_tar\t"
                "reg_ref\tdis_p\tdis_r\tdis_f1\treg_p\treg_r\tref_f1\n")
        for fname, dis_correct, dis_tar, dis_ref, reg_correct, reg_tar, reg_ref in records:
            dis_p, dis_r, dis_f1, reg_p, reg_r, reg_f1 = \
                    compute(dis_correct, dis_tar, dis_ref, reg_correct, reg_tar, reg_ref)
            f.write("%(fname)s\t"
                    "%(dis_correct)d\t%(dis_tar)d\t%(dis_ref)d\t%(reg_correct)d\t"
                    "%(reg_tar)d\t%(reg_ref)d\t%(dis_p)f\t%(dis_r)f\t%(dis_f1)f\t"
                    "%(reg_p)f\t%(reg_r)f\t%(reg_f1)f\n" %locals())
    _log.info("Detailed report written to %s" %os.path.abspath(path))


def write_summarized_report_to_stream(f):
    f.write("type\tdis_correct\tdis_tar\tdis_ref\treg_correct\treg_tar\t"
                "reg_ref\tdis_p\tdis_r\tdis_f1\treg_p\treg_r\tref_f1\n")
    cols = zip(*records)[1:]
    sums = tuple(sum(col) for col in cols)
    dis_correct, dis_tar, dis_ref, reg_correct, reg_tar, reg_ref = sums
    dis_p, dis_r, dis_f1, reg_p, reg_r, reg_f1 = \
            compute(dis_correct, dis_tar, dis_ref, reg_correct, reg_tar, reg_ref)
    f.write("micro\t"
            "%(dis_correct)d\t%(dis_tar)d\t%(dis_ref)d\t%(reg_correct)d\t"
            "%(reg_tar)d\t%(reg_ref)d\t%(dis_p)f\t%(dis_r)f\t%(dis_f1)f\t"
            "%(reg_p)f\t%(reg_r)f\t%(reg_f1)f\n" %locals())
    
    rows = [compute(*r[1:]) for r in records]
    cols = zip(*rows)
    avgs = tuple(sum(col)/len(rows) for col in cols)
    dis_p, dis_r, dis_f1, reg_p, reg_r, reg_f1 = avgs
    f.write("macro\t\t\t\t\t\t\t"
            "%(dis_p)f\t%(dis_r)f\t%(dis_f1)f\t"
            "%(reg_p)f\t%(reg_r)f\t%(reg_f1)f\n" %locals())
    

def write_summarized_report(path):
    _log.info("Writing summarized report...")
    with open(path, "wt") as f:
        write_summarized_report_to_stream(f)
    _log.info("Summarized report written to %s" %os.path.abspath(path))


def write_reports(report_dir):
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)
    write_detailed_report(os.path.join(report_dir, "details.tsv"))
    write_summarized_report(os.path.join(report_dir, "summary.tsv"))
