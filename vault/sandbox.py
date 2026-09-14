import multiprocessing, os

def child(conn, operation, args):
    try:
        if os.name == 'posix':
            import resource
            resource.setrlimit(resource.RLIMIT_AS,(12*1024**3,12*1024**3))
            resource.setrlimit(resource.RLIMIT_CPU,(900,900))
            os.setsid()
            if os.getenv('VAULT_TESTING') != '1':
                if os.getuid() != 0:
                    raise ValueError('Parser isolation is not configured.')
                os.setgroups([])
                os.setgid(65534)
                os.setuid(65534)
                # Dropped identity cannot read application keys or access parent memory.
                os.umask(0o077)
        if operation=='ocr':
            from .ocr import extract
            result=extract(*args)
        elif operation=='sheet':
            from .sheets import parse_book
            result=parse_book(*args)
        else: raise ValueError('Unsupported operation')
        conn.send(('ok',result))
    except Exception as exc:
        from .ocr import DocumentError
        if isinstance(exc,(DocumentError,ValueError)):
            conn.send(('error',str(exc)[:240]))
        else: conn.send(('error','Processing failed: unreadable or unsupported input.'))
    finally: conn.close()

def run(operation,args,timeout):
    ctx=multiprocessing.get_context('spawn'); receiver,sender=ctx.Pipe(duplex=False)
    process=ctx.Process(target=child,args=(sender,operation,args)); process.start(); sender.close()
    try:
        if not receiver.poll(timeout): raise ValueError('Processing time limit exceeded.')
        try: state,value=receiver.recv()
        except EOFError: raise ValueError('Processing stopped: file may exceed resource limits.')
        if state!='ok': raise ValueError(value)
        return value
    finally:
        receiver.close()
        if process.is_alive():
            if os.name=='posix':
                import signal
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: process.terminate()
            else: process.terminate()
        process.join(timeout=5)
