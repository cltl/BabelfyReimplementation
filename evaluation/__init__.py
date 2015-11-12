
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
    correct = sum(1 for span in tar_dict 
                  if span in ref_dict and 
                  tar_dict[span] == ref_dict[span])
    wrong = sum(1 for span in tar_dict 
                if span not in ref_dict or 
                tar_dict[span] != ref_dict[span])
    span_correct = sum(1 for span in tar_dict 
                       if span in ref_dict)
    span_wrong = sum(1 for span in tar_dict 
                       if span not in ref_dict)
    fname = os.path.basename(tar)
    records.append((fname, correct, wrong, span_correct, span_wrong, len(ref_dict)))
    
    
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


def compute(correct, wrong, span_correct, span_wrong, ref_count):
    p = div(correct, correct + wrong) # precision
    r = div(correct, ref_count) # recall
    sp = div(span_correct, span_correct + span_wrong) # span precision
    sr = div(span_correct, ref_count) # span recall
    return p, r, sp, sr
    

def write_detailed_report(path):
    _log.info("Writing detailed report...")
    with open(path, "wt") as f:
        f.write("fname\tcorrect\twrong\tspan_correct\tspan_wrong\t"
                "ref_count\tprecision\trecall\tspan_prec\tspan_recall\n")
        for fname, correct, wrong, span_correct, span_wrong, ref_count in records:
            p, r, sp, sr = compute(correct, wrong, span_correct, span_wrong, ref_count)
            f.write("%(fname)s\t"
                    "%(correct)d\t%(wrong)d\t%(span_correct)d\t%(span_wrong)d\t"
                    "%(ref_count)s\t%(p)f\t%(r)f\t%(sp)f\t%(sr)f\n" %locals())
    _log.info("Detailed report written to %s" %os.path.abspath(path))


def write_summarized_report_to_stream(f):
    f.write("type\ttotal_correct\ttotal_wrong\ttotal_span_correct\ttotal_span_wrong\t"
            "total_ref_count\ttotal_precision\ttotal_recall\ttotal_span_prec\ttotal_span_recall\n")
    _, correct, wrong, span_correct, span_wrong, ref_count = zip(*records)
    total_correct = sum(correct)
    total_wrong = sum(wrong)
    total_span_correct = sum(span_correct)
    total_span_wrong = sum(span_wrong)
    total_ref_count = sum(ref_count)
    total_p, total_r, total_sp, total_sr = compute(total_correct, total_wrong, 
                                                   total_span_correct, 
                                                   total_span_wrong, 
                                                   total_ref_count)
    f.write("micro\t%(total_correct)d\t%(total_wrong)d\t%(total_span_correct)d\t%(total_span_wrong)d\t"
            "%(total_ref_count)s\t%(total_p)f\t%(total_r)f\t%(total_sp)f\t%(total_sr)f\n" %locals())
    
    pr = [compute(correct, wrong, span_correct, span_wrong, ref_count)
          for _, correct, wrong, span_correct, span_wrong, ref_count in records]
    p, r, sp, sr = zip(*pr)
    total_p, total_r, total_sp, total_sr = (sum(p)/len(p), sum(r)/len(r),
                                            sum(sp)/len(sp), sum(sr)/len(sr))
    f.write("macro\t\t\t\t\t"
            "\t%(total_p)f\t%(total_r)f\t%(total_sp)f\t%(total_sr)f\n" %locals())
    

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
