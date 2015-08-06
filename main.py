import cherrypy
import jinja2
import json
import molns
import multiprocessing
import os
import Queue
import traceback

appDir = os.path.dirname(os.path.abspath(__file__))

templateLoader = jinja2.FileSystemLoader(searchpath = "html")
templateEnv = jinja2.Environment(loader = templateLoader)

class Logger(object):
    def __init__(self, queue):
        self.queue = queue

    def write(self, stuff):
        self.queue.put(stuff)

    def flush(self):
        pass

def wrapStdoutStderr(func, stdout, stderr, args = (), kwargs = {}):
    import sys
    import molns
    sys.stdout = stdout
    sys.stderr = stderr

    try:
        func(*args, **kwargs)
    except Exception as e:
        traceback.print_exc()
        print str(e)

    sys.stdout.flush()
    sys.stderr.flush()

def logexceptions(func):
    def inner(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            traceback.print_exc()

            return { 'status' : False, 'msg' : str(e) }

    return inner

def testfunction(a, s, d, f):
    print a
    print s
    print d
    print f

def startMolns(providerName, password, configFilename):
    #print providerName, config
    config = molns.MOLNSConfig(db_file = configFilename)
    molns.MOLNSProvider.provider_initialize(providerName, config)
    molns.MOLNSProvider.provider_get_config(provider_type = 'EC2', config = config)
    molns.MOLNSController.start_controller(['goat'], config, password = password)

def stopMolns(providerName, configFilename):
    config = molns.MOLNSConfig(db_file = configFilename)
    molns.MOLNSController.stop_controller(['goat'], config)

#if __name__ == '__main__':
if False:
    stdout = Logger(multiprocessing.Queue())
    stderr = Logger(multiprocessing.Queue())
    process = multiprocessing.Process(target = wrapStdoutStderr, args = (testfunction, stdout, stderr, ('a', 'b', 'c', 'd')))

    process.start()

    i = 0

    #print stdout.queue.get(False)

    while True:
        try:
            res = stdout.queue.get(False)
            print 'o', i, res
            i += 1
        except Queue.Empty as e:
            break

    while True:
        try:
            res = stderr.queue.get(False)
            print 'e', i, res
            i += 1
        except Queue.Empty as e:
            break

    process.join()

    while True:
        try:
            res = stdout.queue.get(False)
            print 'o', i, res
            i += 1
        except Queue.Empty as e:
            break

    while True:
        try:
            res = stderr.queue.get(False)
            print 'e', i, res
            i += 1
        except Queue.Empty as e:
            break

class App(object):
    @cherrypy.expose
    @logexceptions
    def index(self):
        template = templateEnv.get_template( 'index.html' )

        data = {}

        if 'aws_access_key' not in cherrypy.session:
            data['aws_access_key'] = ''
        else:
            data['aws_access_key'] = cherrypy.session['aws_access_key']

        if 'aws_secret_key' not in cherrypy.session:
            data['aws_access_key'] = ''
        else:
            data['aws_secret_key'] = cherrypy.session['aws_secret_key']

        if 'head_node' not in cherrypy.session:
            data['head_node'] = 'c3.large'
        else:
            data['head_node'] = cherrypy.session['head_node']

        return template.render({ 'json' : json.dumps(data) })

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def savekeys(self, aws_access_key = None, aws_secret_key = None):
        if aws_access_key == None:
            return { 'status' : False, 'msg' : 'Access key must be set' }

        if aws_secret_key == None:
            return { 'status' : False, 'msg' : 'Secret key must be set' }

        if 'aws_access_key' not in cherrypy.session:
            cherrypy.session['aws_access_key'] = aws_access_key

        if 'aws_secret_key' not in cherrypy.session:
            cherrypy.session['aws_secret_key'] = aws_secret_key

        config = molns.MOLNSConfig(db_file="/home/bbales2/molnsconfigserver/test.db")
        provider_conf_items = molns.MOLNSProvider.provider_get_config(provider_type='EC2', config = config)

        json_obj = {}

        for obj in provider_conf_items:
            json_obj[obj['key']] = obj['value']

        json_obj['aws_access_key'] = aws_access_key
        json_obj['aws_secret_key'] = aws_secret_key

        molns.MOLNSProvider.provider_import('', config, json_obj)

        return { 'status' : True, 'msg' : 'Keys set successfully' }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def readstdout(self):
        if 'process' not in cherrypy.session:
            return []

        process, stdout, stderr = cherrypy.session['process']

        output = []

        while True:
            try:
                res = stdout.queue.get(False)
                output.append({ 'status' : 1, 'msg' : res })
            except Queue.Empty as e:
                break

        while True:
            try:
                res = stderr.queue.get(False)
                print res
                output.append({ 'status' : 0, 'msg' : res })
            except Queue.Empty as e:
                break

        return output

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def stopmolns(self):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            return { 'status' : False, 'msg' : 'Currently running process' }

        if 'aws_access_key' not in cherrypy.session:
            cherrypy.session['aws_access_key'] = aws_access_key

        if 'aws_secret_key' not in cherrypy.session:
            cherrypy.session['aws_secret_key'] = aws_secret_key

        if 'head_node' not in cherrypy.session:
            cherrypy.session['head_node'] = head_node

        providerName = 'mountain'

        stdout = Logger(multiprocessing.Queue())
        stderr = Logger(multiprocessing.Queue())
        process = multiprocessing.Process(target = wrapStdoutStderr, args = (stopMolns, stdout, stderr, (providerName, "/home/bbales2/molnsconfigserver/test.db")))
        process.start()

        cherrypy.session['process'] = (process, stdout, stderr)

        return { 'status' : True, 'msg' : 'MOLNs stop request made successfully' }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @logexceptions
    def startmolns(self, pw = None, aws_access_key = None, aws_secret_key = None, head_node = None):
        if 'process' in cherrypy.session and cherrypy.session['process'][0].is_alive():
            return { 'status' : False, 'msg' : 'Currently running process' }
        else:
            session = None

        if pw == None:
            return { 'status' : False, 'msg' : 'Password must be set' }

        if aws_access_key == None:
            return { 'status' : False, 'msg' : 'Access key must be set' }

        if aws_secret_key == None:
            return { 'status' : False, 'msg' : 'Secret key must be set' }

        if head_node == None:
            return { 'status' : False, 'msg' : 'Head node must be set' }

        if 'aws_access_key' not in cherrypy.session:
            cherrypy.session['aws_access_key'] = aws_access_key

        if 'aws_secret_key' not in cherrypy.session:
            cherrypy.session['aws_secret_key'] = aws_secret_key

        if 'head_node' not in cherrypy.session:
            cherrypy.session['head_node'] = head_node

        config = molns.MOLNSConfig(db_file="/home/bbales2/molnsconfigserver/test.db")

        provider_conf_items = molns.MOLNSProvider.provider_get_config(provider_type = 'EC2', config = config)

        json_obj = { 'name' : 'mountain',
                     'type' : 'EC2',
                     'config' : {} }

        providerName = json_obj['name']

        json_obj['config']['aws_access_key'] = aws_access_key
        json_obj['config']['aws_secret_key'] = aws_secret_key

        molns.MOLNSProvider.provider_import('', config, json_obj)

        controller_conf_items = molns.MOLNSController.controller_get_config(provider_type = 'EC2', config = config)

        json_obj = { 'name' : 'goat',
                     'provider_name' : 'mountain',
                     'config' : { 'instance_type' : head_node} }

        molns.MOLNSController.controller_import('', config, json_obj)

        stdout = Logger(multiprocessing.Queue())
        stderr = Logger(multiprocessing.Queue())
        #process = multiprocessing.Process(target = wrapStdoutStderr, args = (testfunction, stdout, stderr, ('a', 'b', 'c', 'd')))
        #process.join()
        #molns.MOLNSProvider.provider_initialize('mountain', config)
        process = multiprocessing.Process(target = wrapStdoutStderr, args = (startMolns, stdout, stderr, (providerName, pw, "/home/bbales2/molnsconfigserver/test.db")))
        #process = multiprocessing.Process(target = molns.MOLNSProvider.provider_initialize, args = (json_obj['name'], config))
        process.start()

        cherrypy.session['process'] = (process, stdout, stderr)

        return { 'status' : True, 'msg' : 'MOLNs start request sent successfully' }

if __name__ == '__main__':
    cherrypy.quickstart(App(), '/', {
        '/' : {
            'tools.gzip.on' : True,
            'log.screen' : True,
            'tools.sessions.on' : True
        },
        '/js' : {
            'tools.staticdir.on' : True,
            'tools.staticdir.dir' : os.path.join(appDir, 'js'),
            'log.screen' : True
        },
    })

    
